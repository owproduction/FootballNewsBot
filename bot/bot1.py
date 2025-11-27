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
            "Месси", "Роналду", "Мбаппе", "Холанд", "Неймар", 
            "Бензема", "Салах", "Де Брейне", "Кейн", "Модрич"
        ]
        
        # Инициализация базы данных для избранного
        self.init_favorites_db()
        
        # Добавляем обработчики
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("news", self.show_news_categories))
        self.application.add_handler(CommandHandler("leagues", self.show_leagues))
        self.application.add_handler(CommandHandler("clubs", self.show_clubs))
        self.application.add_handler(CommandHandler("players", self.show_players_search))
        self.application.add_handler(CommandHandler("stats", self.show_stats))
        self.application.add_handler(CommandHandler("favorites", self.show_favorites))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработчики для текстового ввода - и для игроков, и для клубов
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_search))
        
    def init_favorites_db(self):
        """Инициализирует таблицу для хранения избранного"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER,
                type TEXT, -- 'club' или 'player'
                name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, type, name)
            )
        ''')
        
        conn.commit()
        conn.close()
    
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
            "✨ <b>Новая функция:</b> Добавляйте команды и игроков в избранное!\n\n"
            "Нажми кнопку ниже, чтобы начать просмотр новостей!"
        )
        
        keyboard = [
            [InlineKeyboardButton("📰 Смотреть новости", callback_data="show_news_categories")],
            [InlineKeyboardButton("🏆 Выбрать лигу", callback_data="show_leagues")],
            [InlineKeyboardButton("⚽ Поиск по клубам", callback_data="show_clubs")],
            [InlineKeyboardButton("👤 Поиск по игрокам", callback_data="search_players")],
            [InlineKeyboardButton("⭐ Избранное", callback_data="show_favorites")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_news_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает категории новостей"""
        keyboard = [
            [InlineKeyboardButton("🔥 Все новости", callback_data="news_latest_all")],
            [InlineKeyboardButton("🏆 По лигам", callback_data="show_leagues")],
            [InlineKeyboardButton("⚽ По клубам", callback_data="show_clubs")],
            [InlineKeyboardButton("👤 По игрокам", callback_data="search_players")],
            [InlineKeyboardButton("⭐ Избранное", callback_data="show_favorites")],
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
            # Проверяем, добавлен ли клуб в избранное
            is_favorite = self.is_favorite(update.effective_user.id, 'club', club)
            star = "⭐ " if is_favorite else ""
            row.append(InlineKeyboardButton(f"{star}{club}", callback_data=f"club_{club}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        # Добавляем кнопки управления
        keyboard.append([InlineKeyboardButton("⭐ Мои клубы", callback_data="favorite_clubs")])
        keyboard.append([InlineKeyboardButton("✏️ Ввести клуб вручную", callback_data="manual_club_search")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "⚽ <b>Выберите клуб</b>\n\nПросмотр новостей по выбранному клубу:\n⭐ - добавлено в избранное"
        
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
            "⭐ - добавлено в избранное"
        )
        
        # Создаем кнопки для популярных игроков (по 2 в ряд)
        keyboard = []
        row = []
        for player in self.popular_players:
            # Проверяем, добавлен ли игрок в избранное
            is_favorite = self.is_favorite(update.effective_user.id, 'player', player)
            star = "⭐ " if is_favorite else ""
            row.append(InlineKeyboardButton(f"{star}{player}", callback_data=f"player_{player}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        # Добавляем кнопки управления
        keyboard.append([InlineKeyboardButton("⭐ Мои игроки", callback_data="favorite_players")])
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
            "• Поиск работает по заголовкам новостей\n\n"
            "💡 <i>Совет:</i> Используйте фамилию для более точного поиска"
        )
        
        keyboard = [
            [InlineKeyboardButton("⭐ Мои игроки", callback_data="favorite_players")],
            [InlineKeyboardButton("🔙 К списку игроков", callback_data="search_players")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_manual_club_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает интерфейс ручного ввода названия клуба"""
        text = (
            "⚽ <b>Поиск по клубам - ручной ввод</b>\n\n"
            "Введите название клуба для поиска:\n"
            "• Можно вводить полное название или аббревиатуру\n"
            "• Например: <i>Реал Мадрид</i>, <i>Барселона</i>, <i>Челси</i>\n"
            "• Поиск работает по тегам клубов в новостях\n\n"
            "💡 <i>Совет:</i> Используйте полное название для более точного поиска"
        )
        
        keyboard = [
            [InlineKeyboardButton("⭐ Мои клубы", callback_data="favorite_clubs")],
            [InlineKeyboardButton("🔙 К списку клубов", callback_data="show_clubs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def handle_text_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текстовый поиск - как по игрокам, так и по клубам"""
        search_text = update.message.text.strip()
        
        if len(search_text) < 2:
            await update.message.reply_text(
                "❌ Слишком короткий запрос. Введите минимум 2 символа.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К списку игроков", callback_data="search_players")],
                    [InlineKeyboardButton("🔙 К списку клубов", callback_data="show_clubs")]
                ])
            )
            return
        
        # Определяем тип поиска: проверяем, есть ли такой клуб в базе
        all_clubs = self.get_all_clubs()
        is_club_search = any(search_text.lower() in club.lower() for club in all_clubs)
        
        if is_club_search:
            await self.handle_club_search(update, context, search_text)
        else:
            await self.handle_player_search(update, context, search_text)
    
    async def handle_player_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, player_name: str = None):
        """Обрабатывает поиск по игрокам"""
        if player_name is None:
            player_name = update.message.text.strip()
        
        if len(player_name) < 2:
            await update.message.reply_text(
                "❌ Слишком короткий запрос. Введите минимум 2 символа.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку игроков", callback_data="search_players")]])
            )
            return
        
        # Показываем сообщение о поиске
        search_msg = await update.message.reply_text(f"🔍 Ищу новости по игроку '{player_name}'...")
        
        # Ищем новости по игроку - ТОЛЬКО В ЗАГОЛОВКЕ
        news_items = self.get_news_from_db(limit=50, player=player_name)
        
        # Удаляем сообщение о поиске
        await search_msg.delete()
        
        if not news_items:
            text = (
                f"❌ Новости по игроку '{player_name}' не найдены.\n\n"
                f"Попробуйте:\n"
                f"• Проверить написание имени\n"
                f"• Использовать фамилию\n"
                f"• Попробовать другого игрока\n"
                f"• Выбрать из популярных игроков"
            )
            keyboard = [
                [InlineKeyboardButton("🔙 К списку игроков", callback_data="search_players")],
                [InlineKeyboardButton("✏️ Ввести другое имя", callback_data="manual_player_search")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        # Сохраняем новости в контексте пользователя
        context.user_data['news_items'] = news_items
        context.user_data['current_news_index'] = 0
        context.user_data['current_player'] = player_name
        context.user_data['news_type'] = "player_search"
        
        # Показываем первую новость
        await self.display_news(update, context, 0)
    
    async def handle_club_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, club_name: str = None):
        """Обрабатывает поиск по клубам"""
        if club_name is None:
            club_name = update.message.text.strip()
        
        if len(club_name) < 2:
            await update.message.reply_text(
                "❌ Слишком короткий запрос. Введите минимум 2 символа.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку клубов", callback_data="show_clubs")]])
            )
            return
        
        # Показываем сообщение о поиске
        search_msg = await update.message.reply_text(f"🔍 Ищу новости по клубу '{club_name}'...")
        
        # Ищем новости по клубу
        news_items = self.get_news_from_db(limit=50, club=club_name)
        
        # Удаляем сообщение о поиске
        await search_msg.delete()
        
        if not news_items:
            text = (
                f"❌ Новости по клубу '{club_name}' не найдены.\n\n"
                f"Попробуйте:\n"
                f"• Проверить написание названия\n"
                f"• Использовать полное название\n"
                f"• Попробовать другой клуб\n"
                f"• Выбрать из списка клубов"
            )
            keyboard = [
                [InlineKeyboardButton("🔙 К списку клубов", callback_data="show_clubs")],
                [InlineKeyboardButton("✏️ Ввести другой клуб", callback_data="manual_club_search")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        # Сохраняем новости в контексте пользователя
        context.user_data['news_items'] = news_items
        context.user_data['current_news_index'] = 0
        context.user_data['current_club'] = club_name
        context.user_data['news_type'] = "club_search"
        
        # Показываем первую новость
        await self.display_news(update, context, 0)
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает избранное пользователя"""
        user_id = update.effective_user.id
        favorite_clubs = self.get_favorites(user_id, 'club')
        favorite_players = self.get_favorites(user_id, 'player')
        
        text = "⭐ <b>Ваше избранное</b>\n\n"
        
        if not favorite_clubs and not favorite_players:
            text += "У вас пока нет избранных клубов или игроков.\n\n"
            text += "💡 <i>Чтобы добавить в избранное:</i>\n"
            text += "• При просмотре списка клубов или игроков нажмите на звезду ⭐\n"
            text += "• Или используйте кнопку 'Добавить в избранное' при просмотре новостей"
        else:
            if favorite_clubs:
                text += "🏟 <b>Избранные клубы:</b>\n"
                for club in favorite_clubs:
                    text += f"• {club}\n"
                text += "\n"
            
            if favorite_players:
                text += "👤 <b>Избранные игроки:</b>\n"
                for player in favorite_players:
                    text += f"• {player}\n"
        
        keyboard = []
        
        if favorite_clubs:
            keyboard.append([InlineKeyboardButton("🏟 Новости по избранным клубам", callback_data="favorite_clubs_news")])
        
        if favorite_players:
            keyboard.append([InlineKeyboardButton("👤 Новости по избранным игрокам", callback_data="favorite_players_news")])
        
        keyboard.extend([
            [InlineKeyboardButton("⚽ К клубам", callback_data="show_clubs")],
            [InlineKeyboardButton("👤 К игрокам", callback_data="search_players")],
            [InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_favorite_clubs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает избранные клубы пользователя"""
        user_id = update.effective_user.id
        favorite_clubs = self.get_favorites(user_id, 'club')
        
        if not favorite_clubs:
            text = "⭐ <b>Избранные клубы</b>\n\nУ вас пока нет избранных клубов."
            keyboard = [
                [InlineKeyboardButton("⚽ Добавить клубы", callback_data="show_clubs")],
                [InlineKeyboardButton("🔙 Назад", callback_data="show_favorites")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            return
        
        text = "⭐ <b>Ваши избранные клубы</b>\n\nВыберите клуб для просмотра новостей:"
        
        keyboard = []
        for club in favorite_clubs:
            keyboard.append([InlineKeyboardButton(f"🏟 {club}", callback_data=f"club_{club}")])
        
        keyboard.extend([
            [InlineKeyboardButton("📰 Все новости по избранным клубам", callback_data="favorite_clubs_news")],
            [InlineKeyboardButton("⚽ Добавить ещё клубы", callback_data="show_clubs")],
            [InlineKeyboardButton("🔙 Назад", callback_data="show_favorites")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_favorite_players(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает избранных игроков пользователя"""
        user_id = update.effective_user.id
        favorite_players = self.get_favorites(user_id, 'player')
        
        if not favorite_players:
            text = "⭐ <b>Избранные игроки</b>\n\nУ вас пока нет избранных игроков."
            keyboard = [
                [InlineKeyboardButton("👤 Добавить игроков", callback_data="search_players")],
                [InlineKeyboardButton("🔙 Назад", callback_data="show_favorites")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            return
        
        text = "⭐ <b>Ваши избранные игроки</b>\n\nВыберите игрока для просмотра новостей:"
        
        keyboard = []
        for player in favorite_players:
            keyboard.append([InlineKeyboardButton(f"👤 {player}", callback_data=f"player_{player}")])
        
        keyboard.extend([
            [InlineKeyboardButton("📰 Все новости по избранным игрокам", callback_data="favorite_players_news")],
            [InlineKeyboardButton("👤 Добавить ещё игроков", callback_data="search_players")],
            [InlineKeyboardButton("🔙 Назад", callback_data="show_favorites")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                       club: str = None, league: str = None, player: str = None, news_type: str = "all"):
        """Показывает первую новость"""
        # Сохраняем фильтры в контексте пользователя
        context.user_data['current_club'] = club
        context.user_data['current_league'] = league
        context.user_data['current_player'] = player
        context.user_data['news_type'] = news_type
        
        # Получаем новости
        if news_type == "favorite_clubs":
            favorite_clubs = self.get_favorites(update.effective_user.id, 'club')
            news_items = self.get_news_for_favorite_clubs(favorite_clubs)
        elif news_type == "favorite_players":
            favorite_players = self.get_favorites(update.effective_user.id, 'player')
            news_items = self.get_news_for_favorite_players(favorite_players)
        else:
            news_items = self.get_news_from_db(limit=50, club=club, league=league, player=player)
        
        if not news_items:
            if club:
                text = f"❌ Новости по клубу '{club}' не найдены. Попробуйте другой клуб."
            elif league:
                text = f"❌ Новости по лиге '{league}' не найдены. Попробуйте другую лигу."
            elif player:
                text = f"❌ Новости по игроку '{player}' не найдены. Попробуйте другое имя."
            elif news_type == "favorite_clubs":
                text = "❌ Новости по вашим избранным клубам не найдены."
            elif news_type == "favorite_players":
                text = "❌ Новости по вашим избранным игрокам не найдены."
            else:
                text = "❌ Новости не найдены. Попробуйте позже."
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_news_categories")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query') and update.callback_query:
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
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer("Новости закончились! 🏁", show_alert=True)
            else:
                await update.message.reply_text("Новости закончились! 🏁")
            return
        
        news_item = news_items[index]
        
        # Формируем заголовок с информацией о фильтре
        filter_info = ""
        club = context.user_data.get('current_club')
        league = context.user_data.get('current_league')
        player = context.user_data.get('current_player')
        news_type = context.user_data.get('news_type')
        
        if club:
            filter_info = f" | Клуб: {club}"
        elif league:
            filter_info = f" | Лига: {league}"
        elif player:
            filter_info = f" | Игрок: {player}"
        elif news_type == "favorite_clubs":
            filter_info = " | ⭐ Избранные клубы"
        elif news_type == "favorite_players":
            filter_info = " | ⭐ Избранные игроки"
        
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
        
        # Подсвечиваем имя игрока в заголовке, если есть поиск по игроку
        if player:
            # Находим упоминания игрока в заголовке (регистронезависимо)
            pattern = re.compile(re.escape(player), re.IGNORECASE)
            highlighted_title = pattern.sub(f"<b>{player}</b>", news_item['title'])
            text = f"<b>{highlighted_title}</b>\n\n" + text.split('\n\n', 1)[1]
            
            # Добавляем информацию о поиске
            text += f"\n🔍 <i>Найдено по поиску: '{player}'</i>\n"
        
        # Подсвечиваем название клуба в тегах, если есть поиск по клубу
        elif club:
            # Находим упоминания клуба в тегах (регистронезависимо)
            if news_item.get('club_tags'):
                pattern = re.compile(re.escape(club), re.IGNORECASE)
                highlighted_clubs = pattern.sub(f"<b>{club}</b>", news_item['club_tags'])
                text = text.replace(news_item['club_tags'], highlighted_clubs)
            
            # Добавляем информацию о поиске
            text += f"\n🔍 <i>Найдено по поиску: '{club}'</i>\n"
        
        if news_item.get('link'):
            text += f"\n🔗 <a href='{news_item['link']}'>Читать на сайте</a>"
        
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
        
        # Кнопки добавления в избранное
        favorite_buttons = []
        current_club = context.user_data.get('current_club')
        current_player = context.user_data.get('current_player')
        
        if current_club:
            is_favorite = self.is_favorite(update.effective_user.id, 'club', current_club)
            if is_favorite:
                favorite_buttons.append(InlineKeyboardButton("❌ Удалить клуб из избранного", callback_data=f"remove_favorite_club_{current_club}"))
            else:
                favorite_buttons.append(InlineKeyboardButton("⭐ Добавить клуб в избранное", callback_data=f"add_favorite_club_{current_club}"))
        
        if current_player:
            is_favorite = self.is_favorite(update.effective_user.id, 'player', current_player)
            if is_favorite:
                favorite_buttons.append(InlineKeyboardButton("❌ Удалить игрока из избранного", callback_data=f"remove_favorite_player_{current_player}"))
            else:
                favorite_buttons.append(InlineKeyboardButton("⭐ Добавить игрока в избранное", callback_data=f"add_favorite_player_{current_player}"))
        
        if favorite_buttons:
            keyboard.append(favorite_buttons)
        
        # Дополнительные кнопки
        other_buttons = [
            InlineKeyboardButton("🏠 Главная", callback_data="show_news_categories"),
            InlineKeyboardButton("⭐ Избранное", callback_data="show_favorites")
        ]
        
        # Кнопка возврата к фильтру
        if club:
            other_buttons.append(InlineKeyboardButton("⚽ К клубам", callback_data="show_clubs"))
        elif league:
            other_buttons.append(InlineKeyboardButton("🏆 К лигам", callback_data="show_leagues"))
        elif player:
            # Для ручного поиска добавляем кнопку возврата к поиску
            other_buttons.append(InlineKeyboardButton("👤 Новый поиск", callback_data="search_players"))
        elif news_type == "favorite_clubs":
            other_buttons.append(InlineKeyboardButton("⭐ К избранным клубам", callback_data="favorite_clubs"))
        elif news_type == "favorite_players":
            other_buttons.append(InlineKeyboardButton("⭐ К избранным игрокам", callback_data="favorite_players"))
        
        if other_buttons:
            keyboard.append(other_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем или редактируем сообщение
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            
            # Редактируем существующее сообщение
            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                # Если не удалось отредактировать, отправляем новое сообщение
                await query.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
        else:
            # Отправляем новое сообщение
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
        
        # Статистика по избранному
        user_id = update.effective_user.id
        favorite_clubs_count = len(self.get_favorites(user_id, 'club'))
        favorite_players_count = len(self.get_favorites(user_id, 'player'))
        
        text = (
            f"<b>📊 Статистика базы новостей</b>\n\n"
            f"📰 <b>Всего новостей:</b> {total_news}\n"
            f"🏆 <b>Лиг в базе:</b> {len(leagues)}\n"
            f"⚽ <b>Отслеживаемых клубов:</b> {len(clubs)}\n"
            f"👤 <b>Популярных игроков:</b> {len(self.popular_players)}\n\n"
            f"⭐ <b>Ваше избранное:</b>\n"
            f"• Клубы: {favorite_clubs_count}\n"
            f"• Игроки: {favorite_players_count}\n\n"
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
            [InlineKeyboardButton("⭐ Избранное", callback_data="show_favorites")],
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
        
        elif data == "manual_club_search":
            await self.show_manual_club_search(update, context)
        
        elif data == "show_favorites":
            await self.show_favorites(update, context)
        
        elif data == "favorite_clubs":
            await self.show_favorite_clubs(update, context)
        
        elif data == "favorite_players":
            await self.show_favorite_players(update, context)
        
        elif data == "favorite_clubs_news":
            await self.show_news(update, context, news_type="favorite_clubs")
        
        elif data == "favorite_players_news":
            await self.show_news(update, context, news_type="favorite_players")
        
        elif data.startswith("player_"):
            player = data[7:]  # Убираем префикс "player_"
            await self.show_news(update, context, player=player)
        
        elif data.startswith("league_"):
            league = data[7:]  # Убираем префикс "league_"
            await self.show_news(update, context, league=league)
        
        elif data.startswith("club_"):
            club = data[5:]  # Убираем префикс "club_"
            await self.show_news(update, context, club=club)
        
        elif data.startswith("add_favorite_club_"):
            club = data[18:]  # Убираем префикс "add_favorite_club_"
            user_id = update.effective_user.id
            self.add_favorite(user_id, 'club', club)
            await query.answer(f"✅ Клуб '{club}' добавлен в избранное!")
            # Обновляем текущее сообщение
            current_index = context.user_data.get('current_news_index', 0)
            await self.display_news(update, context, current_index)
        
        elif data.startswith("remove_favorite_club_"):
            club = data[21:]  # Убираем префикс "remove_favorite_club_"
            user_id = update.effective_user.id
            self.remove_favorite(user_id, 'club', club)
            await query.answer(f"❌ Клуб '{club}' удален из избранного")
            # Обновляем текущее сообщение
            current_index = context.user_data.get('current_news_index', 0)
            await self.display_news(update, context, current_index)
        
        elif data.startswith("add_favorite_player_"):
            player = data[20:]  # Убираем префикс "add_favorite_player_"
            user_id = update.effective_user.id
            self.add_favorite(user_id, 'player', player)
            await query.answer(f"✅ Игрок '{player}' добавлен в избранное!")
            # Обновляем текущее сообщение
            current_index = context.user_data.get('current_news_index', 0)
            await self.display_news(update, context, current_index)
        
        elif data.startswith("remove_favorite_player_"):
            player = data[23:]  # Убираем префикс "remove_favorite_player_"
            user_id = update.effective_user.id
            self.remove_favorite(user_id, 'player', player)
            await query.answer(f"❌ Игрок '{player}' удален из избранного")
            # Обновляем текущее сообщение
            current_index = context.user_data.get('current_news_index', 0)
            await self.display_news(update, context, current_index)
        
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
    
    # Методы для работы с избранным
    def add_favorite(self, user_id: int, item_type: str, name: str):
        """Добавляет элемент в избранное"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT OR REPLACE INTO favorites (user_id, type, name) VALUES (?, ?, ?)',
            (user_id, item_type, name)
        )
        
        conn.commit()
        conn.close()
    
    def remove_favorite(self, user_id: int, item_type: str, name: str):
        """Удаляет элемент из избранного"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'DELETE FROM favorites WHERE user_id = ? AND type = ? AND name = ?',
            (user_id, item_type, name)
        )
        
        conn.commit()
        conn.close()
    
    def get_favorites(self, user_id: int, item_type: str = None):
        """Получает избранное пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if item_type:
            cursor.execute(
                'SELECT name FROM favorites WHERE user_id = ? AND type = ? ORDER BY added_at DESC',
                (user_id, item_type)
            )
        else:
            cursor.execute(
                'SELECT type, name FROM favorites WHERE user_id = ? ORDER BY added_at DESC',
                (user_id,)
            )
        
        results = cursor.fetchall()
        conn.close()
        
        if item_type:
            return [row[0] for row in results]
        else:
            return results
    
    def is_favorite(self, user_id: int, item_type: str, name: str) -> bool:
        """Проверяет, есть ли элемент в избранном"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT 1 FROM favorites WHERE user_id = ? AND type = ? AND name = ?',
            (user_id, item_type, name)
        )
        
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    def get_news_for_favorite_clubs(self, clubs: List[str], limit: int = 50):
        """Получает новости для избранных клубов"""
        if not clubs:
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаем условия для LIKE для каждого клуба
        conditions = []
        params = []
        for club in clubs:
            conditions.append('club_tags LIKE ?')
            params.append(f'%{club}%')
        
        query = f'SELECT * FROM news WHERE ({" OR ".join(conditions)}) ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        
        news_items = []
        columns = [column[0] for column in cursor.description]
        
        for row in cursor.fetchall():
            news_item = dict(zip(columns, row))
            news_items.append(news_item)
        
        conn.close()
        return news_items
    
    def get_news_for_favorite_players(self, players: List[str], limit: int = 50):
        """Получает новости для избранных игроков"""
        if not players:
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаем условия для LIKE для каждого игрока
        conditions = []
        params = []
        for player in players:
            conditions.append('title LIKE ?')
            params.append(f'%{player}%')
        
        query = f'SELECT * FROM news WHERE ({" OR ".join(conditions)}) ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        
        news_items = []
        columns = [column[0] for column in cursor.description]
        
        for row in cursor.fetchall():
            news_item = dict(zip(columns, row))
            news_items.append(news_item)
        
        conn.close()
        return news_items
    
    # Методы для работы с базой данных новостей
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
            # ИЩЕМ ТОЛЬКО В ЗАГОЛОВКЕ, так как поля content нет
            query += ' AND title LIKE ?'
            params.append(f'%{player}%')
            
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        # Отладочная информация
        logger.info(f"Поиск новостей: club='{club}', player='{player}', запрос: {query}")
        
        cursor.execute(query, params)
        
        news_items = []
        columns = [column[0] for column in cursor.description]
        
        for row in cursor.fetchall():
            news_item = dict(zip(columns, row))
            news_items.append(news_item)
        
        logger.info(f"Найдено новостей: {len(news_items)}")
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
    
    def check_database_structure(self):
        """Проверяет структуру базы данных для отладки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("Таблицы в базе:", tables)
        
        # Проверяем структуру таблицы news
        cursor.execute("PRAGMA table_info(news)")
        columns = cursor.fetchall()
        print("Структура таблицы news:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Показываем примеры данных (только существующие колонки)
        cursor.execute("SELECT * FROM news LIMIT 3")
        samples = cursor.fetchall()
        print("Примеры новостей (первые 3 записи):")
        for i, sample in enumerate(samples, 1):
            print(f"  {i}. {sample}")
        
        conn.close()
    
    def run(self):
        """Запускает бота"""
        print("Бот запущен...")
        print("Доступные команды:")
        print("/start - Начать работу")
        print("/news - Показать новости")
        print("/leagues - Выбрать лигу")
        print("/clubs - Выбрать клуб")
        print("/players - Поиск по игрокам")
        print("/favorites - Избранное")
        print("/stats - Статистика")
        print(f"\nПопулярные игроки для поиска: {', '.join(self.popular_players)}")
        print("\n🔍 Теперь можно искать новости по клубам и игрокам с клавиатуры!")
        
        # Проверяем структуру базы данных при запуске
        print("\n=== ПРОВЕРКА СТРУКТУРЫ БАЗЫ ДАННЫХ ===")
        self.check_database_structure()
        print("=== КОНЕЦ ПРОВЕРКИ ===\n")
        
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