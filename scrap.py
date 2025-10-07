import requests
from bs4 import BeautifulSoup
import time
import json
import csv
import os
from datetime import datetime
import random
import sqlite3
from contextlib import contextmanager

class SportboxDatabaseScraper:
    def __init__(self, db_path='sportbox_news.db'):
        self.db_path = db_path
        self.init_database()
        
    @contextmanager
    def get_db_connection(self):
        """Контекстный менеджер для работы с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Создаем таблицу новостей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    link TEXT UNIQUE NOT NULL,
                    rubric TEXT,
                    date TEXT,
                    image_url TEXT,
                    content TEXT,
                    scraped_at DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Создаем индекс для быстрого поиска по ссылкам
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_link ON news(link)
            ''')
            
            # Создаем индекс для поиска по дате
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_scraped_at ON news(scraped_at)
            ''')
    
    def news_exists(self, link):
        """Проверяем, существует ли новость в БД"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM news WHERE link = ?', (link,))
            return cursor.fetchone() is not None
    
    def save_news_to_db(self, news_items):
        """Сохраняем новости в базу данных"""
        new_count = 0
        updated_count = 0
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            for item in news_items:
                if not item['link']:
                    continue
                
                # Проверяем существование новости
                if self.news_exists(item['link']):
                    # Обновляем существующую запись
                    cursor.execute('''
                        UPDATE news 
                        SET title = ?, rubric = ?, date = ?, image_url = ?, scraped_at = ?
                        WHERE link = ?
                    ''', (
                        item['title'],
                        item['rubric'],
                        item['date'],
                        item['image_url'],
                        item['scraped_at'],
                        item['link']
                    ))
                    if cursor.rowcount > 0:
                        updated_count += 1
                else:
                    # Вставляем новую запись
                    cursor.execute('''
                        INSERT INTO news (title, link, rubric, date, image_url, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        item['title'],
                        item['link'],
                        item['rubric'],
                        item['date'],
                        item['image_url'],
                        item['scraped_at']
                    ))
                    new_count += 1
        
        return new_count, updated_count
    
    def get_page_content(self, url):
        """Получаем контент страницы"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Ошибка загрузки страницы: {e}")
            return None

    def parse_news(self, html_content):
        """Парсим новости"""
        soup = BeautifulSoup(html_content, 'html.parser')
        news_items = []
        
        # Ищем новости в разных возможных контейнерах
        selectors = [
            '.news-item',
            '.teaser-item',
            '.b-news-list li',
            '.b-teasers-list li',
            '.item-news',
            '[class*="news"]',
            '[class*="teaser"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f"Найдено элементов по селектору {selector}: {len(elements)}")
                for element in elements:
                    news_item = self.extract_news_data(element)
                    if news_item and news_item['title'] and len(news_item['title']) > 10:
                        news_items.append(news_item)
                break
        
        # Если не нашли стандартными селекторами, ищем по структуре
        if not news_items:
            print("Поиск по альтернативным селекторам...")
            # Ищем любые ссылки с заголовками
            links = soup.find_all('a', href=True)
            for link in links:
                if len(link.get_text(strip=True)) > 20 and '/news/' in link['href']:
                    news_item = {
                        'title': link.get_text(strip=True),
                        'link': 'https://news.sportbox.ru' + link['href'] if not link['href'].startswith('http') else link['href'],
                        'rubric': '',
                        'date': '',
                        'image_url': '',
                        'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    news_items.append(news_item)
        
        return news_items

    def extract_news_data(self, element):
        """Извлекаем данные новости"""
        try:
            # Заголовок
            title_elem = element.select_one('.title .text, .teaser-title, .news-title, .b-teaser__title, .b-news__title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Ссылка
            link_elem = element.find('a')
            link = link_elem.get('href') if link_elem else ""
            if link and not link.startswith('http'):
                link = 'https://news.sportbox.ru' + link
            
            # Рубрика
            rubric_elem = element.select_one('.rubric, .teaser-rubric, .news-rubric, .b-teaser__rubric, .b-news__rubric')
            rubric = rubric_elem.get_text(strip=True) if rubric_elem else ""
            
            # Дата
            date_elem = element.select_one('.date, .teaser-date, .news-date, .b-teaser__date, .b-news__date')
            date = date_elem.get_text(strip=True) if date_elem else ""
            
            # Изображение
            img_elem = element.find('img')
            image_url = img_elem.get('src') if img_elem else ""
            if image_url and not image_url.startswith('http'):
                image_url = 'https:' + image_url
            
            return {
                'title': title,
                'link': link,
                'rubric': rubric,
                'date': date,
                'image_url': image_url,
                'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            print(f"Ошибка извлечения: {e}")
            return None

    def scrape(self, url, pages=3):
        """Основная функция парсинга"""
        all_news = []
        
        for page in range(1, pages + 1):
            print(f"Парсим страницу {page}...")
            
            if page == 1:
                page_url = url
            else:
                page_url = f"{url}?page={page}"
            
            html = self.get_page_content(page_url)
            if html:
                news = self.parse_news(html)
                all_news.extend(news)
                print(f"Собрано новостей: {len(news)}")
            
            if page < pages:
                time.sleep(random.uniform(2, 4))
        
        # Сохраняем в БД
        if all_news:
            new_count, updated_count = self.save_news_to_db(all_news)
            print(f"Добавлено новых: {new_count}, обновлено: {updated_count}")
        
        return all_news

    def export_to_files(self, format_type='both'):
        """Экспорт данных из БД в файлы"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, link, rubric, date, image_url, scraped_at 
                FROM news 
                ORDER BY scraped_at DESC
            ''')
            news = [dict(row) for row in cursor.fetchall()]
        
        if not news:
            print("Нет данных для экспорта")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_type in ['json', 'both']:
            # JSON
            with open(f'sportbox_news_export_{timestamp}.json', 'w', encoding='utf-8') as f:
                json.dump(news, f, ensure_ascii=False, indent=2)
            print(f"JSON экспорт создан: sportbox_news_export_{timestamp}.json")
        
        if format_type in ['csv', 'both']:
            # CSV
            with open(f'sportbox_news_export_{timestamp}.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=news[0].keys())
                writer.writeheader()
                writer.writerows(news)
            print(f"CSV экспорт создан: sportbox_news_export_{timestamp}.csv")

    def get_statistics(self):
        """Получаем статистику по базе данных"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Общее количество новостей
            cursor.execute('SELECT COUNT(*) FROM news')
            total_count = cursor.fetchone()[0]
            
            # Количество новостей по рубрикам
            cursor.execute('''
                SELECT rubric, COUNT(*) as count 
                FROM news 
                WHERE rubric IS NOT NULL AND rubric != '' 
                GROUP BY rubric 
                ORDER BY count DESC
            ''')
            rubric_stats = cursor.fetchall()
            
            # Последняя дата обновления
            cursor.execute('SELECT MAX(scraped_at) FROM news')
            last_update = cursor.fetchone()[0]
            
        return {
            'total_news': total_count,
            'rubric_stats': dict(rubric_stats),
            'last_update': last_update
        }

    def get_news_by_rubric(self, rubric, limit=10):
        """Получаем новости по рубрике"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, link, rubric, date, image_url, scraped_at 
                FROM news 
                WHERE rubric = ? 
                ORDER BY scraped_at DESC 
                LIMIT ?
            ''', (rubric, limit))
            return [dict(row) for row in cursor.fetchall()]

    def search_news(self, search_term, limit=10):
        """Поиск новостей по заголовку"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, link, rubric, date, image_url, scraped_at 
                FROM news 
                WHERE title LIKE ? 
                ORDER BY scraped_at DESC 
                LIMIT ?
            ''', (f'%{search_term}%', limit))
            return [dict(row) for row in cursor.fetchall()]

def main():
    # Создаем экземпляр парсера
    scraper = SportboxDatabaseScraper()
    
    # URL для парсинга
    url = "https://news.sportbox.ru/Vidy_sporta/Futbol/Liga_Chempionov"
    
    # Запускаем парсинг
    print("Запуск парсинга...")
    news = scraper.scrape(url, pages=3)
    
    # Показываем статистику
    stats = scraper.get_statistics()
    print(f"\n=== СТАТИСТИКА ===")
    print(f"Всего новостей в базе: {stats['total_news']}")
    print(f"Распределение по рубрикам: {stats['rubric_stats']}")
    print(f"Последнее обновление: {stats['last_update']}")
    
    # Экспортируем данные
    print("\nЭкспорт данных...")
    scraper.export_to_files('both')
    
    # Показываем последние новости
    print(f"\n=== ПОСЛЕДНИЕ НОВОСТИ ===")
    with scraper.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title, rubric, date, scraped_at 
            FROM news 
            ORDER BY scraped_at DESC 
            LIMIT 5
        ''')
        for i, row in enumerate(cursor.fetchall(), 1):
            print(f"{i}. {row['title']}")
            print(f"   Рубрика: {row['rubric']}, Дата: {row['date']}")

if __name__ == "__main__":
    main()