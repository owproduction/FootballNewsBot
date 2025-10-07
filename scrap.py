import requests
from bs4 import BeautifulSoup
import time
import json
import csv
import os
from datetime import datetime
import random
import sqlite3
from typing import List, Dict

class SimpleSportboxScraper:
    def __init__(self, db_path: str = "football_news.db"):
        self.news_data = []
        self.db_path = db_path
        os.makedirs('sportbox_news', exist_ok=True)
        self.init_database()
        
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT UNIQUE,
                rubric TEXT,
                date TEXT,
                image_url TEXT,
                scraped_at TEXT,
                club_tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем индекс для быстрого поиска по заголовку и тегам
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_title ON news(title)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_club_tags ON news(club_tags)
        ''')
        
        conn.commit()
        conn.close()
        print(f"База данных инициализирована: {self.db_path}")
        
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

    def extract_club_tags(self, title: str) -> str:
        """Извлекает теги клубов из заголовка"""
        clubs = {
            'Реал Мадрид': ['реал', 'мадрид', 'real madrid'],
            'Барселона': ['барселона', 'barcelona', 'барса'],
            'Манчестер Юнайтед': ['манчестер юнайтед', 'manchester united', 'ман юнайтед'],
            'Челси': ['челси', 'chelsea'],
            'Бавария': ['бавария', 'bayern', 'бавария мюнхен'],
            'Ювентус': ['ювентус', 'juventus'],
            'Ливерпуль': ['ливерпуль', 'liverpool'],
            'Арсенал': ['арсенал', 'arsenal'],
            'Манчестер Сити': ['манчестер сити', 'manchester city'],
            'Милан': ['милан', 'milan'],
            'Интер': ['интер', 'inter'],
            'ПСЖ': ['псж', 'psg', 'пари сен-жермен'],
            'Боруссия Дортмунд': ['боруссия', 'dortmund', 'дортмунд']
        }
        
        found_clubs = []
        title_lower = title.lower()
        
        for club, keywords in clubs.items():
            if any(keyword in title_lower for keyword in keywords):
                found_clubs.append(club)
                
        return ', '.join(found_clubs) if found_clubs else ''

    def parse_news(self, html_content):
        """Парсим новости"""
        soup = BeautifulSoup(html_content, 'html.parser')
        news_items = []
        
        # Ищем новости в разных возможных контейнерах
        selectors = [
            '#teazers ul.list li',
            '.teaser-list .teaser-item',
            '.news-list .news-item',
            '.b-news-list .b-news-item',
            '.news-item',
            '.teaser-item'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f"Найдено элементов по селектору {selector}: {len(elements)}")
                for element in elements:
                    news_item = self.extract_news_data(element)
                    if news_item and news_item['title']:
                        news_items.append(news_item)
                break
        
        return news_items

    def extract_news_data(self, element):
        """Извлекаем данные новости"""
        try:
            # Заголовок
            title_elem = element.select_one('.title .text, .teaser-title, .news-title, .b-news-title, .title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Ссылка
            link_elem = element.find('a')
            link = link_elem.get('href') if link_elem else ""
            if link and not link.startswith('http'):
                link = 'https://news.sportbox.ru' + link
            
            # Рубрика
            rubric_elem = element.select_one('.rubric, .teaser-rubric, .news-rubric, .b-news-rubric')
            rubric = rubric_elem.get_text(strip=True) if rubric_elem else ""
            
            # Дата
            date_elem = element.select_one('.date, .teaser-date, .news-date, .b-news-date')
            date = date_elem.get_text(strip=True) if date_elem else ""
            
            # Изображение
            img_elem = element.find('img')
            image_url = img_elem.get('src') if img_elem else ""
            if image_url and not image_url.startswith('http'):
                image_url = 'https:' + image_url
            
            # Извлекаем теги клубов
            club_tags = self.extract_club_tags(title)
            
            return {
                'title': title,
                'link': link,
                'rubric': rubric,
                'date': date,
                'image_url': image_url,
                'club_tags': club_tags,
                'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            print(f"Ошибка извлечения: {e}")
            return None

    def save_to_database(self, news_items: List[Dict]):
        """Сохраняет новости в базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        for item in news_items:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO news 
                    (title, link, rubric, date, image_url, scraped_at, club_tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item['title'],
                    item['link'],
                    item['rubric'],
                    item['date'],
                    item['image_url'],
                    item['scraped_at'],
                    item.get('club_tags', '')
                ))
                saved_count += 1
            except sqlite3.IntegrityError:
                # Пропускаем дубликаты (UNIQUE constraint on link)
                continue
            except Exception as e:
                print(f"Ошибка сохранения новости в БД: {e}")
        
        conn.commit()
        conn.close()
        print(f"Сохранено новых новостей в БД: {saved_count}")
        
    def get_news_from_db(self, limit: int = 100, club: str = None):
        """Получает новости из базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if club:
            cursor.execute('''
                SELECT * FROM news 
                WHERE club_tags LIKE ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (f'%{club}%', limit))
        else:
            cursor.execute('''
                SELECT * FROM news 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
        
        news_items = []
        columns = [column[0] for column in cursor.description]
        
        for row in cursor.fetchall():
            news_item = dict(zip(columns, row))
            news_items.append(news_item)
        
        conn.close()
        return news_items
    
    def get_all_clubs(self):
        """Получает список всех клубов из базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT club_tags FROM news 
            WHERE club_tags != '' 
            AND club_tags IS NOT NULL
        ''')
        
        clubs = set()
        for row in cursor.fetchall():
            club_list = row[0].split(', ')
            clubs.update(club_list)
        
        conn.close()
        return sorted(list(clubs))
    
    def get_news_count(self):
        """Получает общее количество новостей в базе"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM news')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count

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
        
        # Сохраняем в базу данных
        if all_news:
            self.save_to_database(all_news)
        
        return all_news

    def save_data(self, data):
        """Сохраняем данные в файлы и базу данных"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON
        with open(f'sportbox_news/sportbox_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # CSV
        if data:
            with open(f'sportbox_news/sportbox_{timestamp}.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        
        print(f"Данные сохранены в sportbox_news/sportbox_{timestamp}.[json|csv]")
        print(f"Всего новостей в базе данных: {self.get_news_count()}")

def main():
    scraper = SimpleSportboxScraper()
    url = "https://news.sportbox.ru/Vidy_sporta/Futbol/Liga_Chempionov"
    
    news = scraper.scrape(url, pages=3)
    
    if news:
        scraper.save_data(news)
        print(f"Успешно собрано {len(news)} новостей!")
        
        # Показываем первые 5 новостей
        for i, item in enumerate(news[:5]):
            print(f"\n{i+1}. {item['title']}")
            print(f"   Рубрика: {item['rubric']}")
            print(f"   Дата: {item['date']}")
            print(f"   Клубы: {item.get('club_tags', 'Не указаны')}")
        
        # Показываем доступные клубы
        clubs = scraper.get_all_clubs()
        print(f"\nДоступные клубы в базе: {', '.join(clubs)}")
        
        # Тестируем получение новостей по клубу
        if clubs:
            test_club = clubs[0]
            club_news = scraper.get_news_from_db(limit=3, club=test_club)
            print(f"\nПоследние новости по {test_club}:")
            for i, item in enumerate(club_news):
                print(f"  {i+1}. {item['title']}")
                
    else:
        print("Не удалось собрать новости")

if __name__ == "__main__":
    main()