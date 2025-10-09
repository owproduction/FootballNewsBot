import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import sqlite3
from typing import List, Dict
import os
import re

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
        
        # 10 самых популярных футболистов для быстрого поиска
        self.popular_players = [
            "Месси", "Роналду", "Мбаппе", "Халанд", "Неймар", 
            "Бензема", "Салех", "Де Брейне", "Кейн", "Модрич"
        ]
        
        # Добавляем обработчики
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("news", self.show_news_categories))
        self.application.add_handler(CommandHandler("leagues", self.show_leagues))
        self.application.add_handler(CommandHandler("clubs", self.show_clubs))
        self.application.add_handler(CommandHandler("players", self.show_players_search))
        self.application.add_handler(CommandHandler("stats", self.show_stats))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_player_search))
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_text = (
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот с последними футбольными новостями из Sportbox.\n"
            "Я поддерживаю все основные европейские лиги:\n"
            "• Английская Премьер-лига 🏴󠁧󠁢󠁥󠁮󠁧󠁿\n"
            "• Ла Лига 🇪🇸\n"
            "• Серия А 🇮🇹\n"
            "• Бундеслига 🇩🇪\n"
            "• Лига 1 🇫🇷\n"
            "• Лига Чемпионов 🏆\n"
            "• Лига Европы 🥈\n"
            "• РПЛ 🇷🇺\n\n"
            "Нажми кнопку ниже, чтобы начать просмотр новостей!"
        )
        
        keyboard = [
            [InlineKeyboardButton("📰 Смотреть новости", callback_data="show_news_categories")],
            [InlineKeyboardButton("🏆 Выбрать лигу", callback_data="show_leagues")],
            [InlineKeyboardButton("⚽ Поиск по клубам", callback_data="show_clubs")],
            [InlineKeyboardButton("👤 Поиск по игрокам", callback_data="search_players")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def show_news_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает категории новостей"""
        keyboard = [
            [InlineKeyboardButton("🔥 Все новости", callback_data="news_latest_all")],
            [InlineKeyboardButton("🏆 По лигам", callback_data="show_leagues")],
            [InlineKeyboardButton("⚽ По клубам", callback_data="show_clubs")],
            [InlineKeyboardButton("👤 По игрокам", callback_data="search_players")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "📰 <b>Категории новостей</b>\n\nВыберите как хотите просматривать новости:"
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_leagues(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список лиг"""
        leagues = self.get_all_leagues()
        
        if not leagues:
            text = "❌ Пока нет новостей по лигам. Попробуйте позже."
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(text, reply_markup=reply_markup)
            else:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            return
        
        # Эмодзи для лиг
        league_emojis = {
            'Английская Премьер-лига': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
            'Ла Лига': '🇪🇸',
            'Серия А': '🇮🇹',
            'Бундеслига': '🇩🇪',
            'Лига 1': '🇫🇷',
            'Лига Чемпионов': '🏆',
            'Лига Европы': '🥈',
            'Российская Премьер-лига': '🇷🇺'
        }
        
        # Создаем кнопки для лиг
        keyboard = []
        for league in leagues:
            emoji = league_emojis.get(league, '⚽')
            keyboard.append([InlineKeyboardButton(f"{emoji} {league}", callback_data=f"league_{league}")])
        
        # Добавляем кнопку назад
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "🏆 <b>Выберите лигу</b>\n\nПросмотр новостей по выбранной лиге:"
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_clubs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список клубов для фильтрации"""
        clubs = self.get_all_clubs()
        
        if not clubs:
            text = "❌ Пока нет новостей с тегами клубов. Попробуйте позже."
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(text, reply_markup=reply_markup)
            else:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            return
        
        # Создаем кнопки для клубов (по 2 в ряд)
        keyboard = []
        row = []
        for club in clubs[:20]:  # Ограничиваем до 20 клубов
            row.append(InlineKeyboardButton(club, callback_data=f"club_{club}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        # Добавляем кнопку назад
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "⚽ <b>Выберите клуб</b>\n\nПросмотр новостей по выбранному клубу:"
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_players_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает интерфейс поиска по игрокам"""
        text = (
            "👤 <b>Поиск новостей по игрокам</b>\n\n"
            "Выберите одного из популярных игроков или введите имя игрока вручную:\n"
            "• Поиск работает по заголовкам новостей\n"
            "• Можно вводить фамилию или полное имя\n"
        )
        
        # Создаем кнопки для популярных игроков (по 2 в ряд)
        keyboard = []
        row = []
        for player in self.popular_players:
            row.append(InlineKeyboardButton(player, callback_data=f"player_{player}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        # Добавляем кнопку ручного ввода и назад
        keyboard.append([InlineKeyboardButton("✏️ Ввести имя вручную", callback_data="manual_player_search")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_manual_player_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает интерфейс ручного ввода имени игрока"""
        text = (
            "👤 <b>Поиск по игрокам - ручной ввод</b>\n\n"
            "Введите имя игрока для поиска:\n"
            "• Можно вводить фамилию или полное имя\n"
            "• Например: <i>Месси</i>, <i>Роналду</i>, <i>Мбаппе</i>\n"
            "• Поиск работает по заголовкам новостей"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 К списку игроков", callback_data="search_players")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def handle_player_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает поиск по игрокам"""
        player_name = update.message.text.strip()
        
        if len(player_name) < 2:
            await update.message.reply_text(
                "❌ Слишком короткий запрос. Введите минимум 2 символа.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку игроков", callback_data="search_players")]])
            )
            return
        
        # Сохраняем имя игрока для использования в callback
        context.user_data['player_search'] = player_name
        
        # Ищем новости по игроку
        await self.show_news(update, context, player=player_name)
    
    async def show_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                       club: str = None, league: str = None, player: str = None, news_type: str = "all"):
        """Показывает первую новость"""
        # Сохраняем фильтры в контексте пользователя
        context.user_data['current_club'] = club
        context.user_data['current_league'] = league
        context.user_data['current_player'] = player
        context.user_data['news_type'] = news_type
        
        # Получаем новости
        news_items = self.get_news_from_db(limit=50, club=club, league=league, player=player)
        
        if not news_items:
            if club:
                text = f"❌ Новости по клубу '{club}' не найдены. Попробуйте другой клуб."
            elif league:
                text = f"❌ Новости по лиге '{league}' не найдены. Попробуйте другую лигу."
            elif player:
                text = f"❌ Новости по игроку '{player}' не найдены. Попробуйте другое имя."
            else:
                text = "❌ Новости не найдены. Попробуйте позже."
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query'):
                query = update.callback_query
                await query.edit_message_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)
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
            if hasattr(update, 'callback_query'):
                await update.callback_query.answer("Новости закончились! 🏁", show_alert=True)
            return
        
        news_item = news_items[index]
        
        # Формируем заголовок с информацией о фильтре
        filter_info = ""
        club = context.user_data.get('current_club')
        league = context.user_data.get('current_league')
        player = context.user_data.get('current_player')
        
        if club:
            filter_info = f" | Клуб: {club}"
        elif league:
            filter_info = f" | Лига: {league}"
        elif player:
            filter_info = f" | Игрок: {player}"
        
        # Формируем текст новости
        text = f"<b>{news_item['title']}</b>\n\n"
        
        if news_item.get('rubric'):
            text += f"🏷 <b>Рубрика:</b> {news_item['rubric']}\n"
        
        if news_item.get('date'):
            text += f"📅 <b>Дата:</b> {news_item['date']}\n"
        
        if news_item.get('league'):
            text += f"🏆 <b>Лига:</b> {news_item['league']}\n"
        
        if news_item.get('club_tags'):
            text += f"⚽ <b>Клубы:</b> {news_item['club_tags']}\n"
        
        # УБРАНА СТРОКА С ДАТОЙ СБОРА НОВОСТИ (scraped_at)
        # if news_item.get('scraped_at'):
        #     text += f"⏰ <b>Собрано:</b> {news_item['scraped_at']}\n"
        
        # Подсвечиваем имя игрока в заголовке, если есть поиск по игроку
        if player:
            # Находим упоминания игрока в заголовке (регистронезависимо)
            pattern = re.compile(re.escape(player), re.IGNORECASE)
            highlighted_title = pattern.sub(f"<b>{player}</b>", news_item['title'])
            text = f"<b>{highlighted_title}</b>\n\n" + text.split('\n\n', 1)[1]
            
            # Добавляем информацию о поиске
            text += f"\n🔍 <i>Найдено по поиску: '{player}'</i>\n"
        
        if news_item.get('link'):
            text += f"\n🔗 <a href='{news_item['link']}'>Читать на Sportbox</a>"
        
        # Создаем клавиатуру
        keyboard = []
        
        # Кнопки навигации
        nav_buttons = []
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="news_prev"))
        
        nav_buttons.append(InlineKeyboardButton(f"{index + 1}/{len(news_items)}", callback_data="page_info"))
        
        if index < len(news_items) - 1:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data="news_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Дополнительные кнопки
        other_buttons = [
            InlineKeyboardButton("🏠 Главная", callback_data="show_news_categories")
        ]
        
        # Кнопка возврата к фильтру
        if club:
            other_buttons.append(InlineKeyboardButton("⚽ К клубам", callback_data="show_clubs"))
        elif league:
            other_buttons.append(InlineKeyboardButton("🏆 К лигам", callback_data="show_leagues"))
        elif player:
            other_buttons.append(InlineKeyboardButton("👤 К игрокам", callback_data="search_players"))
        
        if other_buttons:
            keyboard.append(other_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем или редактируем сообщение
        if hasattr(update, 'callback_query'):
            query = update.callback_query
            
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
        else:
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику"""
        total_news = self.get_news_count()
        leagues = self.get_all_leagues()
        clubs = self.get_all_clubs()
        
        text = (
            f"<b>📊 Статистика базы новостей</b>\n\n"
            f"📰 <b>Всего новостей:</b> {total_news}\n"
            f"🏆 <b>Лиг в базе:</b> {len(leagues)}\n"
            f"⚽ <b>Отслеживаемых клубов:</b> {len(clubs)}\n"
            f"👤 <b>Популярных игроков:</b> {len(self.popular_players)}\n\n"
        )
        
        # Статистика по лигам
        if leagues:
            text += "<b>Статистика по лигам:</b>\n"
            for league in leagues:
                league_news_count = self.get_news_count(league=league)
                text += f"• {league}: {league_news_count} новостей\n"
        
        # Популярные клубы
        if clubs:
            text += f"\n<b>Клубы в базе:</b>\n{', '.join(clubs[:10])}"
            if len(clubs) > 10:
                text += f" и ещё {len(clubs) - 10}..."
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить статистику", callback_data="stats")],
            [InlineKeyboardButton("🏠 Главная", callback_data="show_news_categories")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "show_news_categories":
            await self.show_news_categories(update, context)
        
        elif data == "news_latest_all":
            await self.show_news(update, context)
        
        elif data == "show_leagues":
            await self.show_leagues(update, context)
        
        elif data == "show_clubs":
            await self.show_clubs(update, context)
        
        elif data == "search_players":
            await self.show_players_search(update, context)
        
        elif data == "manual_player_search":
            await self.show_manual_player_search(update, context)
        
        elif data.startswith("player_"):
            player = data[7:]  # Убираем префикс "player_"
            await self.show_news(update, context, player=player)
        
        elif data.startswith("league_"):
            league = data[7:]  # Убираем префикс "league_"
            await self.show_news(update, context, league=league)
        
        elif data.startswith("club_"):
            club = data[5:]  # Убираем префикс "club_"
            await self.show_news(update, context, club=club)
        
        elif data == "news_next":
            current_index = context.user_data.get('current_news_index', 0)
            context.user_data['current_news_index'] = current_index + 1
            await self.display_news(update, context, current_index + 1)
        
        elif data == "news_prev":
            current_index = context.user_data.get('current_news_index', 0)
            context.user_data['current_news_index'] = current_index - 1
            await self.display_news(update, context, current_index - 1)
        
        elif data == "stats":
            await self.show_stats(update, context)
        
        elif data == "page_info":
            # Просто показываем информацию о текущей странице
            current_index = context.user_data.get('current_news_index', 0)
            news_items = context.user_data.get('news_items', [])
            await query.answer(f"Страница {current_index + 1} из {len(news_items)}")
    
    # Методы для работы с базой данных
    def get_news_from_db(self, limit: int = 100, club: str = None, league: str = None, player: str = None):
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
            
        if player:
            # Ищем только в заголовке, так как поле content отсутствует в текущем парсере
            query += ' AND title LIKE ?'
            params.append(f'%{player}%')
            
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
            clubs.update([club.strip() for club in club_list if club.strip()])
        
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
            ORDER BY league
        ''')
        
        leagues = [row[0] for row in cursor.fetchall() if row[0]]
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
    
    def run(self):
        """Запускает бота"""
        print("Бот запущен...")
        print("Доступные команды:")
        print("/start - Начать работу")
        print("/news - Показать новости")
        print("/leagues - Выбрать лигу")
        print("/clubs - Выбрать клуб")
        print("/players - Поиск по игрокам")
        print("/stats - Статистика")
        print(f"\nПопулярные игроки для поиска: {', '.join(self.popular_players)}")
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