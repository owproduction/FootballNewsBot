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
        
        # URL-адреса для разных лиг
        self.league_urls = {
           'champions_league': "https://news.sportbox.ru/Vidy_sporta/Futbol/Liga_Chempionov",
            'premier_league': "https://news.sportbox.ru/Vidy_sporta/Futbol/Evropejskie_chempionaty/Angliya",
            'la_liga': "https://news.sportbox.ru/Vidy_sporta/Futbol/Evropejskie_chempionaty/Ispaniya",
            'serie_a': "https://news.sportbox.ru/Vidy_sporta/Futbol/Evropejskie_chempionaty/Italiya",
            'bundesliga': "https://news.sportbox.ru/Vidy_sporta/Futbol/Evropejskie_chempionaty/Germaniya",
            'ligue_1': "https://news.sportbox.ru/Vidy_sporta/Futbol/Evropejskie_chempionaty/Franciya",
            'europa_league': "https://news.sportbox.ru/Vidy_sporta/Futbol/europa_league",
            'rpl': "https://news.sportbox.ru/Vidy_sporta/Futbol/Russia/premier_league"
        }
        
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу, если она не существует
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
        
        # Создаем индексы для быстрого поиска
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
            print(f"Ошибка загрузки страницы {url}: {e}")
            return None

    def extract_club_tags(self, title: str, league: str = "") -> str:
        """Извлекает теги клубов из заголовка с учетом лиги"""
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
            'Ростов': ['ростов', 'rostov']
        }
        
        found_clubs = []
        title_lower = title.lower()
        
        for club, keywords in clubs.items():
            if any(keyword in title_lower for keyword in keywords):
                found_clubs.append(club)
                
        return ', '.join(found_clubs) if found_clubs else ''

    def parse_news(self, html_content, league_name=""):
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
            '.teaser-item',
            '.b-news-teaser-item',
            '.b-news-list__item'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f"Найдено элементов по селектору {selector}: {len(elements)}")
                for element in elements:
                    news_item = self.extract_news_data(element, league_name)
                    if news_item and news_item['title']:
                        news_items.append(news_item)
                break
        
        return news_items

    def extract_news_data(self, element, league_name=""):
        """Извлекаем данные новости"""
        try:
            # Заголовок
            title_elem = element.select_one('.title .text, .teaser-title, .news-title, .b-news-title, .title, .b-news-teaser-item__title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Ссылка
            link_elem = element.find('a')
            link = link_elem.get('href') if link_elem else ""
            if link and not link.startswith('http'):
                link = 'https://news.sportbox.ru' + link
            
            # Рубрика
            rubric_elem = element.select_one('.rubric, .teaser-rubric, .news-rubric, .b-news-rubric, .b-news-teaser-item__rubric')
            rubric = rubric_elem.get_text(strip=True) if rubric_elem else ""
            
            # Дата
            date_elem = element.select_one('.date, .teaser-date, .news-date, .b-news-date, .b-news-teaser-item__date')
            date = date_elem.get_text(strip=True) if date_elem else ""
            
            # Изображение
            img_elem = element.find('img')
            image_url = img_elem.get('src') if img_elem else ""
            if image_url and not image_url.startswith('http'):
                image_url = 'https:' + image_url
            
            # Извлекаем теги клубов
            club_tags = self.extract_club_tags(title, league_name)
            
            return {
                'title': title,
                'link': link,
                'rubric': rubric,
                'date': date,
                'image_url': image_url,
                'club_tags': club_tags,
                'league': league_name,
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
                saved_count += 1
            except sqlite3.IntegrityError:
                # Пропускаем дубликаты (UNIQUE constraint on link)
                continue
            except Exception as e:
                print(f"Ошибка сохранения новости в БД: {e}")
        
        conn.commit()
        conn.close()
        print(f"Сохранено новых новостей в БД: {saved_count}")
        
    def get_news_from_db(self, limit: int = 100, club: str = None, league: str = None):
        """Получает новости из базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM news WHERE 1=1'
        params = []
        
        if club:
            query += ' AND club_tags LIKE ?'
            params.append(f'%{club}%')
        
        if league:
            query += ' AND league = ?'
            params.append(league)
            
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        
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
    
    def get_all_leagues(self):
        """Получает список всех лиг из базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT league FROM news 
            WHERE league != '' 
            AND league IS NOT NULL
        ''')
        
        leagues = [row[0] for row in cursor.fetchall()]
        conn.close()
        return sorted(list(set(leagues)))
    
    def get_news_count(self, league: str = None):
        """Получает общее количество новостей в базе"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if league:
            cursor.execute('SELECT COUNT(*) FROM news WHERE league = ?', (league,))
        else:
            cursor.execute('SELECT COUNT(*) FROM news')
            
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def scrape_league(self, league_key: str, league_name: str, pages: int = 3):
        """Парсит конкретную лигу"""
        if league_key not in self.league_urls:
            print(f"Неизвестная лига: {league_key}")
            return []
            
        url = self.league_urls[league_key]
        all_news = []
        
        print(f"\n=== Парсим лигу: {league_name} ===")
        
        for page in range(1, pages + 1):
            print(f"Парсим страницу {page}...")
            
            if page == 1:
                page_url = url
            else:
                page_url = f"{url}?page={page}"
            
            html = self.get_page_content(page_url)
            if html:
                news = self.parse_news(html, league_name)
                all_news.extend(news)
                print(f"Собрано новостей: {len(news)}")
            
            if page < pages:
                time.sleep(random.uniform(2, 4))
        
        # Сохраняем в базу данных
        if all_news:
            self.save_to_database(all_news)
        
        return all_news

    def scrape_all_leagues(self, pages: int = 2):
        """Парсит все лиги"""
        all_news = []
        leagues_to_scrape = {
            'champions_league': 'Лига Чемпионов',
            'premier_league': 'Английская Премьер-лига',
            'la_liga': 'Ла Лига',
            'serie_a': 'Серия А',
            'bundesliga': 'Бундеслига',
            'ligue_1': 'Лига 1',
            'europa_league': 'Лига Европы',
            'rpl': 'Российская Премьер-лига'
        }
        
        for league_key, league_name in leagues_to_scrape.items():
            news = self.scrape_league(league_key, league_name, pages)
            all_news.extend(news)
            print(f"Всего собрано для {league_name}: {len(news)} новостей")
            time.sleep(random.uniform(3, 6))  # Пауза между лигами
        
        return all_news

    def save_data(self, data, filename_suffix=""):
        """Сохраняем данные в файлы и базу данных"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if filename_suffix:
            filename_suffix = f"_{filename_suffix}"
        
        # JSON
        json_filename = f'sportbox_news/sportbox_{timestamp}{filename_suffix}.json'
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # CSV
        if data:
            csv_filename = f'sportbox_news/sportbox_{timestamp}{filename_suffix}.csv'
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        
        print(f"Данные сохранены в sportbox_news/sportbox_{timestamp}{filename_suffix}.[json|csv]")
        print(f"Всего новостей в базе данных: {self.get_news_count()}")

    def print_statistics(self):
        """Печатает статистику по лигам"""
        print("\n=== СТАТИСТИКА БАЗЫ ДАННЫХ ===")
        total_news = self.get_news_count()
        print(f"Всего новостей: {total_news}")
        
        leagues = self.get_all_leagues()
        for league in leagues:
            count = self.get_news_count(league)
            print(f"{league}: {count} новостей")
        
        clubs = self.get_all_clubs()
        print(f"\nКлубы в базе: {', '.join(clubs)}")

def main():
    scraper = SimpleSportboxScraper()
    
    print("Выберите опцию:")
    print("1 - Парсить все лиги")
    print("2 - Парсить конкретную лигу")
    print("3 - Только статистика")
    
    choice = input("Введите номер (1-3): ").strip()
    
    if choice == "1":
        # Парсим все лиги
        news = scraper.scrape_all_leagues(pages=2)
        
        if news:
            scraper.save_data(news, "all_leagues")
            print(f"\nУспешно собрано {len(news)} новостей со всех лиг!")
            
            # Показываем первые 3 новости из каждой лиги
            leagues = scraper.get_all_leagues()
            for league in leagues:
                league_news = scraper.get_news_from_db(limit=3, league=league)
                print(f"\n--- Последние новости {league} ---")
                for i, item in enumerate(league_news):
                    print(f"{i+1}. {item['title']}")
        
    elif choice == "2":
        # Парсим конкретную лигу
        print("\nДоступные лиги:")
        leagues = {
            '1': ('champions_league', 'Лига Чемпионов'),
            '2': ('premier_league', 'Английская Премьер-лига'),
            '3': ('la_liga', 'Ла Лига'),
            '4': ('serie_a', 'Серия А'),
            '5': ('bundesliga', 'Бундеслига'),
            '6': ('ligue_1', 'Лига 1'),
            '7': ('europa_league', 'Лига Европы'),
            '8': ('rpl', 'Российская Премьер-лига')
        }
        
        for key, (_, name) in leagues.items():
            print(f"{key} - {name}")
        
        league_choice = input("Выберите лигу (1-8): ").strip()
        
        if league_choice in leagues:
            league_key, league_name = leagues[league_choice]
            pages = int(input("Сколько страниц парсить? (1-5): ") or "2")
            
            news = scraper.scrape_league(league_key, league_name, pages)
            
            if news:
                scraper.save_data(news, league_key)
                print(f"\nУспешно собрано {len(news)} новостей для {league_name}!")
                
                # Показываем первые 5 новостей
                for i, item in enumerate(news[:5]):
                    print(f"\n{i+1}. {item['title']}")
                    print(f"   Рубрика: {item['rubric']}")
                    print(f"   Дата: {item['date']}")
                    print(f"   Клубы: {item.get('club_tags', 'Не указаны')}")
        else:
            print("Неверный выбор лиги")
    
    elif choice == "3":
        # Только статистика
        scraper.print_statistics()
    
    else:
        print("Неверный выбор")

if __name__ == "__main__":
    main()