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
import re

class ChampionatScraper:
    def __init__(self, db_path: str = r"D:\Kisl\top_college_tver\FootballNewsBot\bot\football_news.db"):
        self.news_data = []
        self.db_path = db_path
        os.makedirs('championat_news', exist_ok=True)
        self.init_database()  # Добавляем инициализацию БД
        
        # Базовый URL для парсинга
        self.base_url = "https://www.championat.com"
        self.news_url = "https://www.championat.com/news/football/1.html"
        
    def init_database(self):
        """Инициализация базы данных (такая же как у Sportbox)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Создаем таблицу, если она не существует (такая же как у Sportbox)
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
                    league TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Проверяем существование колонки league и добавляем если нужно
            cursor.execute("PRAGMA table_info(news)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'league' not in columns:
                print("Добавляем колонку 'league' в таблицу...")
                cursor.execute('ALTER TABLE news ADD COLUMN league TEXT')
            
            # Создаем индексы для быстрого поиска (как у Sportbox)
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_title ON news(title)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_club_tags ON news(club_tags)
            ''')
            
            # Создаем индекс для league только если колонка существует
            if 'league' in columns:
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_league ON news(league)
                ''')
            
            conn.commit()
            conn.close()
            print(f"База данных инициализирована: {self.db_path}")
        except Exception as e:
            print(f"Ошибка инициализации БД: {e}")
        
    def clean_title(self, title):
        """Очищает заголовок от времени и дат в конце (такая же логика как у Sportbox)"""
        if not title:
            return title
        
        # Убираем время в формате HH:MM или HH:MM:SS в конце строки
        cleaned_title = re.sub(r'\s*\d{1,2}:\d{2}(?::\d{2})?\s*$', '', title).strip()
        
        # Убираем даты в формате DD Month (например: "24 ноября", "1 декабря")
        months = [
            'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
            'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
        ]
        
        # Паттерн для дат типа "24 ноября", "1 декабря" и т.д.
        date_pattern = r'\s*\d{1,2}\s+(?:' + '|'.join(months) + r')\s*$'
        cleaned_title = re.sub(date_pattern, '', cleaned_title).strip()
        
        # Убираем комбинации дата + время (например: "24 ноября 03:12")
        datetime_pattern = r'\s*\d{1,2}\s+(?:' + '|'.join(months) + r')\s+\d{1,2}:\d{2}(?::\d{2})?\s*$'
        cleaned_title = re.sub(datetime_pattern, '', cleaned_title).strip()
        
        return cleaned_title

    def get_page_content(self, url):
        """Получаем контент страницы"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Referer': 'https://www.championat.com/',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Ошибка загрузки страницы {url}: {e}")
            return None

    def extract_club_tags(self, title: str, league: str = "") -> str:
        """Извлекает теги клубов из заголовка (такая же логика как у Sportbox)"""
        clubs = {
            # Английская Премьер-лига
            'Манчестер Юнайтед': ['манчестер юнайтед', 'manchester united', 'ман юнайтед'],
            'Манчестер Сити': ['манчестер сити', 'manchester city'],
            'Ливерпуль': ['ливерпуль', 'liverpool'],
            'Челси': ['челси', 'chelsea'],
            'Арсенал': ['арсенал', 'arsenal'],
            'Тоттенхэм': ['тоттенхэм', 'tottenham'],
            'Ньюкасл': ['ньюкасл', 'newcastle'],
            'Астон Вилла': ['астон вилла', 'aston villa'],
            'Вест Хэм': ['вест хэм', 'west ham'],
            'Брайтон': ['брайтон', 'brighton'],
            
            # Ла Лига
            'Реал Мадрид': ['реал', 'мадрид', 'real madrid'],
            'Барселона': ['барселона', 'barcelona', 'барса'],
            'Атлетико Мадрид': ['атлетико мадрид', 'atletico madrid'],
            'Севилья': ['севилья', 'sevilla'],
            'Валенсия': ['валенсия', 'valencia'],
            'Вильярреал': ['вильярреал', 'villarreal'],
            'Атлетик Бильбао': ['атлетик бильбао', 'athletic bilbao'],
            'Реал Сосьедад': ['реал сосьедад', 'real sociedad'],
            
            # Серия А
            'Ювентус': ['ювентус', 'juventus'],
            'Милан': ['милан', 'milan'],
            'Интер': ['интер', 'inter'],
            'Наполи': ['наполи', 'napoli'],
            'Рома': ['рома', 'roma'],
            'Лацио': ['лацио', 'lazio'],
            'Аталанта': ['аталанта', 'atalanta'],
            'Фиорентина': ['фиорентина', 'fiorentina'],
            
            # Бундеслига
            'Бавария': ['бавария', 'bayern', 'бавария мюнхен'],
            'Боруссия Дортмунд': ['боруссия', 'dortmund', 'дортмунд', 'borussia dortmund'],
            'Байер Леверкузен': ['байер леверкузен', 'bayer leverkusen', 'леверкузен'],
            'РБ Лейпциг': ['рб лейпциг', 'rb leipzig', 'лейпциг'],
            'Боруссия Мёнхенгладбах': ['боруссия мёнхенгладбах', 'borussia mönchengladbach'],
            'Айнтрахт Франкфурт': ['айнтрахт франкфурт', 'eintracht frankfurt'],
            'Вольфсбург': ['вольфсбург', 'wolfsburg'],
            'Хоффенхайм': ['хоффенхайм', 'hoffenheim'],
            
            # Лига 1
            'ПСЖ': ['псж', 'psg', 'пари сен-жермен'],
            'Марсель': ['марсель', 'marseille'],
            'Лион': ['лион', 'lyon'],
            'Монако': ['монако', 'monaco'],
            'Лилль': ['лилль', 'lille'],
            'Ренн': ['ренн', 'rennes'],
            'Ницца': ['ница', 'nice'],
            
            # Лига Чемпионов/Европы
            'Байерн': ['байерн', 'bayern'],
            'Реал': ['реал', 'real'],
            'Барса': ['барса', 'barca'],
            'Ман Юнайтед': ['ман юнайтед', 'man united'],
            'Ман Сити': ['ман сити', 'man city'],
            
            # Российская Премьер-лига
            'Зенит': ['зенит', 'zenit'],
            'Спартак': ['спартак', 'spartak'],
            'ЦСКА': ['цска', 'cska'],
            'Локомотив': ['локомотив', 'lokomotiv'],
            'Динамо': ['динамо', 'dynamo'],
            'Краснодар': ['краснодар', 'krasnodar'],
            'Ростов': ['ростов', 'rostov'],
            'Крылья Советов': ['крылья советов', 'крылья'],
            'Ахмат': ['ахмат', 'akhmat'],
            'Сочи': ['сочи', 'sochi'],
            'Оренбург': ['оренбург', 'orenburg'],
            'Урал': ['урал', 'ural'],
            'Балтика': ['балтика', 'baltika'],
            'Пари Нижний Новгород': ['пари нижний новгород', 'пари нн', 'нижний новгород']
        }
        
        found_clubs = []
        title_lower = title.lower()
        
        for club, keywords in clubs.items():
            if any(keyword in title_lower for keyword in keywords):
                found_clubs.append(club)
                
        return ', '.join(found_clubs) if found_clubs else ''

    def parse_news(self, html_content):
        """Парсим новости с championat.com"""
        soup = BeautifulSoup(html_content, 'html.parser')
        news_items = []
        
        # Ищем контейнер с новостями
        news_container = soup.find('div', class_='news-items')
        
        if not news_container:
            print("Не найден контейнер с новостями")
            return news_items
        
        # Получаем дату со страницы
        date_header = news_container.find('div', class_='news-items__head')
        page_date = date_header.get_text(strip=True) if date_header else ""
        
        # Ищем все новости
        news_elements = news_container.find_all('div', class_='news-item')
        
        print(f"Найдено новостей: {len(news_elements)}")
        
        for element in news_elements:
            news_item = self.extract_news_data(element, page_date)
            if news_item and news_item['title']:
                news_items.append(news_item)
        
        return news_items

    def extract_news_data(self, element, page_date):
        """Извлекаем данные новости из элемента"""
        try:
            # Заголовок
            title_elem = element.find('a', class_='news-item__title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Очищаем заголовок от времени и дат
            title = self.clean_title(title)
            
            # Ссылка
            link = title_elem.get('href') if title_elem else ""
            if link and not link.startswith('http'):
                link = self.base_url + link
            
            # Рубрика (лига)
            rubric_elem = element.find('a', class_='news-item__tag')
            rubric = rubric_elem.get_text(strip=True) if rubric_elem else ""
            
            # Время
            time_elem = element.find('div', class_='news-item__time')
            time_str = time_elem.get_text(strip=True) if time_elem else ""
            
            # Формируем полную дату
            date = ""
            if page_date and time_str:
                date = f"{page_date} {time_str}"
            elif page_date:
                date = page_date
            elif time_str:
                date = time_str
            
            # Изображение (если есть)
            img_elem = element.find('img')
            image_url = img_elem.get('src') if img_elem else ""
            if image_url and not image_url.startswith('http'):
                image_url = 'https:' + image_url
            
            # Извлекаем теги клубов
            club_tags = self.extract_club_tags(title)
            
            # Определяем лигу на основе рубрики
            league = self.determine_league(rubric)
            
            return {
                'title': title,
                'link': link,
                'rubric': rubric,
                'date': date,
                'image_url': image_url,
                'club_tags': club_tags,
                'league': league,
                'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            print(f"Ошибка извлечения новости: {e}")
            return None

    def determine_league(self, rubric: str) -> str:
        """Определяет лигу на основе рубрики"""
        league_mapping = {
            'Премьер-лига': 'Российская Премьер-лига',
            'РПЛ': 'Российская Премьер-лига',
            'Кубок России': 'Кубок России',
            'АПЛ': 'Английская Премьер-лига',
            'Англия': 'Английская Премьер-лига',
            'Ла Лига': 'Ла Лига',
            'Испания': 'Ла Лига',
            'Серия А': 'Серия А',
            'Италия': 'Серия А',
            'Бундеслига': 'Бундеслига',
            'Германия': 'Бундеслига',
            'Лига 1': 'Лига 1',
            'Франция': 'Лига 1',
            'Лига Чемпионов': 'Лига Чемпионов',
            'ЛЧ': 'Лига Чемпионов',
            'Лига Европы': 'Лига Европы',
            'ЛЕ': 'Лига Европы',
        }
        
        for key, value in league_mapping.items():
            if key.lower() in rubric.lower():
                return value
        
        return rubric  # Возвращаем оригинальную рубрику если не нашли соответствие

    def save_to_database(self, news_items: List[Dict]):
        """Сохраняет новости в базу данных (такая же логика как у Sportbox)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            saved_count = 0
            for item in news_items:
                try:
                    # Убедимся, что заголовок очищен (как у Sportbox)
                    item['title'] = self.clean_title(item['title'])
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO news 
                        (title, link, rubric, date, image_url, scraped_at, club_tags, league)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        item['title'],
                        item['link'],
                        item['rubric'],
                        item['date'],
                        item['image_url'],
                        item['scraped_at'],
                        item.get('club_tags', ''),
                        item.get('league', '')
                    ))
                    if cursor.rowcount > 0:
                        saved_count += 1
                except sqlite3.IntegrityError:
                    # Пропускаем дубликаты (UNIQUE constraint on link)
                    continue
                except Exception as e:
                    print(f"Ошибка сохранения новости в БД: {e}")
            
            conn.commit()
            conn.close()
            print(f"Сохранено новых новостей в БД: {saved_count}")
            return saved_count
        except Exception as e:
            print(f"Ошибка подключения к БД: {e}")
            return 0
        
    def scrape_news(self, pages: int = 3):
        """Парсит новости с championat.com"""
        all_news = []
        
        print(f"\n=== Парсим championat.com ===\n")
        
        for page in range(1, pages + 1):
            print(f"Парсим страницу {page}...")
            
            if page == 1:
                page_url = self.news_url
            else:
                page_url = f"https://www.championat.com/news/football/{page}.html"
            
            html = self.get_page_content(page_url)
            if html:
                news = self.parse_news(html)
                all_news.extend(news)
                print(f"Собрано новостей: {len(news)}")
            
            if page < pages:
                time.sleep(random.uniform(2, 4))
        
        # Сохраняем в базу данных
        if all_news:
            saved_count = self.save_to_database(all_news)
            print(f"Успешно добавлено в БД: {saved_count} новостей")
        
        return all_news

    def save_data(self, data, filename_suffix=""):
        """Сохраняем данные в файлы (как у Sportbox)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if filename_suffix:
            filename_suffix = f"_{filename_suffix}"
        
        # Очищаем заголовки перед сохранением в файлы (как у Sportbox)
        for item in data:
            item['title'] = self.clean_title(item['title'])
        
        # JSON
        json_filename = f'championat_news/championat_{timestamp}{filename_suffix}.json'
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # CSV
        if data:
            csv_filename = f'championat_news/championat_{timestamp}{filename_suffix}.csv'
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        
        print(f"Данные сохранены в championat_news/championat_{timestamp}{filename_suffix}.[json|csv]")
        print(f"Всего новостей в базе данных: {self.get_news_count()}")

    def get_news_count(self):
        """Получает общее количество новостей в базе (как у Sportbox)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM news')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"Ошибка получения количества новостей: {e}")
            return 0

def main():
    scraper = ChampionatScraper()
    
    print("Парсер championat.com")
    print("Выберите опцию:")
    print("1 - Парсить новости (по умолчанию 3 страницы)")
    print("2 - Указать количество страниц")
    print("3 - Статистика базы данных")
    
    choice = input("Введите номер (1-3): ").strip()
    
    if choice == "1":
        news = scraper.scrape_news(pages=3)
        if news:
            scraper.save_data(news, "championat")
            print(f"\nУспешно собрано {len(news)} новостей с championat.com!")
            
            # Показываем первые 5 новостей
            print("\n--- Последние новости ---")
            for i, item in enumerate(news[:5]):
                print(f"\n{i+1}. {item['title']}")
                print(f"   Рубрика: {item['rubric']}")
                print(f"   Дата: {item['date']}")
                print(f"   Клубы: {item.get('club_tags', 'Не указаны')}")
                print(f"   Лига: {item.get('league', 'Не указана')}")
        
    elif choice == "2":
        pages = int(input("Сколько страниц парсить? (1-10): ") or "3")
        pages = max(1, min(10, pages))  # Ограничиваем от 1 до 10
        
        news = scraper.scrape_news(pages=pages)
        if news:
            scraper.save_data(news, f"championat_{pages}pages")
            print(f"\nУспешно собрано {len(news)} новостей с {pages} страниц!")
    
    elif choice == "3":
        count = scraper.get_news_count()
        print(f"\nСтатистика базы данных:")
        print(f"Всего новостей в базе: {count}")
    
    else:
        print("Неверный выбор")

if __name__ == "__main__":
    main()