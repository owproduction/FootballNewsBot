import requests
from bs4 import BeautifulSoup
import time
import json
import csv
import os
from datetime import datetime
import random

class SimpleSportboxScraper:
    def __init__(self):
        self.news_data = []
        os.makedirs('sportbox_news', exist_ok=True)
        
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
            '#teazers ul.list li',
            '.teaser-list .teaser-item',
            '.news-list .news-item'
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
            title_elem = element.select_one('.title .text, .teaser-title, .news-title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Ссылка
            link_elem = element.find('a')
            link = link_elem.get('href') if link_elem else ""
            if link and not link.startswith('http'):
                link = 'https://news.sportbox.ru' + link
            
            # Рубрика
            rubric_elem = element.select_one('.rubric, .teaser-rubric, .news-rubric')
            rubric = rubric_elem.get_text(strip=True) if rubric_elem else ""
            
            # Дата
            date_elem = element.select_one('.date, .teaser-date, .news-date')
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
        
        return all_news

    def save_data(self, data):
        """Сохраняем данные"""
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

def main():
    scraper = SimpleSportboxScraper()
    url = "https://news.sportbox.ru/Vidy_sporta/Futbol/Liga_Chempionov"
    
    news = scraper.scrape(url, pages=3)
    
    if news:
        scraper.save_data(news)
        print(f"Успешно собрано {len(news)} новостей!")
        
        # Показываем первые 3 новости
        for i, item in enumerate(news[:90]):
            print(f"\n{i+1}. {item['title']}")
            print(f"   Рубрика: {item['rubric']}")
            print(f"   Дата: {item['date']}")
    else:
        print("Не удалось собрать новости")

if __name__ == "__main__":
    main()