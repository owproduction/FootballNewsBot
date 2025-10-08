import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3
from typing import List, Dict
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class FootballNewsBot:
    def __init__(self, token: str, db_path: str = "football_news.db"):
        self.token = token
        self.db_path = db_path
        self.application = Application.builder().token(token).build()
        
        # Добавляем обработчики
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("news", self.show_news_categories))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_text = (
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот с последними футбольными новостями из Sportbox.\n"
            "Нажми кнопку ниже, чтобы начать просмотр новостей!"
        )
        
        keyboard = [
            [InlineKeyboardButton("📰 Смотреть новости", callback_data="show_news_categories")],
            [InlineKeyboardButton("🏆 Поиск по клубам", callback_data="show_clubs")],
            [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def show_news_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает категории новостей"""
        keyboard = [
            [InlineKeyboardButton("🔥 Последние новости", callback_data="news_latest")],
            [InlineKeyboardButton("🏆 По клубам", callback_data="show_clubs")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "Выберите категорию новостей:"
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_clubs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список клубов для фильтрации"""
        clubs = self.get_all_clubs()
        
        if not clubs:
            text = "Пока нет новостей с тегами клубов. Попробуйте позже."
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query = update.callback_query
            await query.edit_message_text(text, reply_markup=reply_markup)
            return
        
        # Создаем кнопки для клубов (по 2 в ряд)
        keyboard = []
        row = []
        for club in clubs:
            row.append(InlineKeyboardButton(club, callback_data=f"club_{club}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        # Добавляем кнопку назад
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "Выберите клуб для просмотра новостей:"
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE, club: str = None):
        """Показывает первую новость"""
        # Сохраняем текущий клуб в контексте пользователя
        if club:
            context.user_data['current_club'] = club
        else:
            context.user_data['current_club'] = None
        
        # Получаем новости
        news_items = self.get_news_from_db(limit=50, club=club)
        
        if not news_items:
            text = "❌ Новости не найдены. Попробуйте другой клуб или зайдите позже."
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query = update.callback_query
            await query.edit_message_text(text, reply_markup=reply_markup)
            return
        
        # Сохраняем новости в контексте пользователя
        context.user_data['news_items'] = news_items
        context.user_data['current_news_index'] = 0
        
        # Показываем первую новость
        await self.display_news(update, context, 0)
    
    async def display_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE, index: int):
        """Отображает новость по индексу"""
        news_items = context.user_data.get('news_items', [])
        
        if not news_items or index >= len(news_items):
            await update.callback_query.answer("Новости закончились!", show_alert=True)
            return
        
        news_item = news_items[index]
        
        # Формируем текст новости
        text = f"<b>{news_item['title']}</b>\n\n"
        
        if news_item.get('rubric'):
            text += f"🏷 <b>Рубрика:</b> {news_item['rubric']}\n"
        
        if news_item.get('date'):
            text += f"📅 <b>Дата:</b> {news_item['date']}\n"
        
        if news_item.get('club_tags'):
            text += f"⚽ <b>Клубы:</b> {news_item['club_tags']}\n"
        
        if news_item.get('scraped_at'):
            text += f"⏰ <b>Собрано:</b> {news_item['scraped_at']}\n"
        
        if news_item.get('link'):
            text += f"\n🔗 <a href='{news_item['link']}'>Читать на Sportbox</a>"
        
        # Создаем клавиатуру
        keyboard = []
        
        # Кнопки навигации
        nav_buttons = []
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="news_prev"))
        
        nav_buttons.append(InlineKeyboardButton(f"{index + 1}/{len(news_items)}", callback_data="stats"))
        
        if index < len(news_items) - 1:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data="news_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Дополнительные кнопки
        other_buttons = []
        if news_item.get('image_url'):
            other_buttons.append(InlineKeyboardButton("🖼 Изображение", callback_data=f"image_{index}"))
        
        other_buttons.append(InlineKeyboardButton("🏠 Главная", callback_data="show_news_categories"))
        
        if other_buttons:
            keyboard.append(other_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем или редактируем сообщение
        query = update.callback_query
        
        # Если есть изображение и пользователь запросил его
        if query.data and query.data.startswith('image_'):
            if news_item.get('image_url'):
                try:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=news_item['image_url'],
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                    return
                except Exception as e:
                    logger.error(f"Ошибка отправки изображения: {e}")
                    text += "\n\n❌ Не удалось загрузить изображение"
        
        # Редактируем существующее сообщение или отправляем новое
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            await query.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику"""
        total_news = self.get_news_count()
        clubs = self.get_all_clubs()
        
        text = (
            f"<b>📊 Статистика базы новостей</b>\n\n"
            f"📰 Всего новостей: <b>{total_news}</b>\n"
            f"🏆 Отслеживаемых клубов: <b>{len(clubs)}</b>\n\n"
            f"<b>Клубы в базе:</b>\n"
        )
        
        for club in clubs:
            club_news_count = len(self.get_news_from_db(club=club, limit=1000))
            text += f"• {club}: {club_news_count} новостей\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает информацию о боте"""
        text = (
            "<b>ℹ️ О боте</b>\n\n"
            "Этот бот показывает последние футбольные новости с сайта Sportbox.ru\n\n"
            "⚙️ <b>Функции:</b>\n"
            "• Просмотр последних новостей\n"
            "• Фильтрация по клубам\n"
            "• Навигация между новостями\n"
            "• Статистика базы данных\n\n"
            "📚 <b>Данные:</b> Новости автоматически собираются и обновляются\n"
            "🔗 <b>Источник:</b> news.sportbox.ru"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "show_news_categories":
            await self.show_news_categories(update, context)
        
        elif data == "news_latest":
            await self.show_news(update, context)
        
        elif data == "show_clubs":
            await self.show_clubs(update, context)
        
        elif data.startswith("club_"):
            club = data[5:]  # Убираем префикс "club_"
            await self.show_news(update, context, club)
        
        elif data == "news_next":
            current_index = context.user_data.get('current_news_index', 0)
            context.user_data['current_news_index'] = current_index + 1
            await self.display_news(update, context, current_index + 1)
        
        elif data == "news_prev":
            current_index = context.user_data.get('current_news_index', 0)
            context.user_data['current_news_index'] = current_index - 1
            await self.display_news(update, context, current_index - 1)
        
        elif data.startswith("image_"):
            index = int(data[6:])  # Получаем индекс из callback_data
            await self.display_news(update, context, index)
        
        elif data == "stats":
            await self.show_stats(update, context)
        
        elif data == "about":
            await self.about(update, context)
    
    # Методы для работы с базой данных (аналогичные классу SimpleSportboxScraper)
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
    
    def run(self):
        """Запускает бота"""
        print("Бот запущен...")
        self.application.run_polling()

# Функция для запуска бота
def run_bot():
    # Токен бота (замените на свой)
    BOT_TOKEN = "8280366470:AAFtYOsUnJ_J1IWdrh0MEExGrD6BPfOeos4"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Пожалуйста, установите ваш токен бота!")
        print("1. Создайте бота через @BotFather в Telegram")
        print("2. Замените 'YOUR_BOT_TOKEN_HERE' на полученный токен")
        return
    
    bot = FootballNewsBot(BOT_TOKEN)
    bot.run()

if __name__ == "__main__":
    run_bot()