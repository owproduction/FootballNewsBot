import os
import json
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
import asyncio

# Импорт вашего парсера
from scrap import SimpleSportboxScraper

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
MAIN_MENU, VIEWING_NEWS, VIEWING_CLUB_NEWS = range(3)

class FootballNewsBot:
    def __init__(self, token: str):
        self.token = token
        self.scraper = SimpleSportboxScraper()
        self.news_data = []
        self.current_news_index = {}
        self.user_states = {}
        
    async def start(self, update: Update, context: CallbackContext) -> int:
        """Начало работы с ботом"""
        user = update.message.from_user
        logger.info(f"Пользователь {user.first_name} начал работу с ботом")
        
        # Инициализация состояния пользователя
        user_id = user.id
        self.current_news_index[user_id] = 0
        
        # Парсим новости при старте (можно кэшировать)
        if not self.news_data:
            await update.message.reply_text("🔄 Загружаю свежие новости...")
            self.news_data = await self.get_news_data()
        
        keyboard = [
            [KeyboardButton("📰 Смотреть все новости")],
            [KeyboardButton("🏆 Смотреть новости по конкретному клубу")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "⚽ Добро пожаловать в футбольный новостной бот!\n"
            "Выберите опцию:",
            reply_markup=reply_markup
        )
        
        return MAIN_MENU

    async def get_news_data(self):
        """Получение данных новостей (можно добавить кэширование)"""
        try:
            # URL для парсинга (можно изменить на нужный)
            url = "https://news.sportbox.ru/Vidy_sporta/Futbol"
            news = self.scraper.scrape(url, pages=2)
            return news
        except Exception as e:
            logger.error(f"Ошибка при парсинге новостей: {e}")
            return []

    async def show_main_menu(self, update: Update, context: CallbackContext) -> int:
        """Показ главного меню"""
        keyboard = [
            [KeyboardButton("📰 Смотреть все новости")],
            [KeyboardButton("🏆 Смотреть новости по конкретному клубу")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=reply_markup
        )
        
        return MAIN_MENU

    async def show_all_news(self, update: Update, context: CallbackContext) -> int:
        """Показ всех новостей"""
        user_id = update.message.from_user.id
        
        if not self.news_data:
            await update.message.reply_text("❌ Новости временно недоступны. Попробуйте позже.")
            return await self.show_main_menu(update, context)
        
        # Сбрасываем индекс для пользователя
        self.current_news_index[user_id] = 0
        
        # Показываем первую новость
        await self.show_current_news(update, context, user_id)
        
        return VIEWING_NEWS

    async def show_current_news(self, update: Update, context: CallbackContext, user_id: int):
        """Показ текущей новости"""
        if self.current_news_index[user_id] >= len(self.news_data):
            await update.message.reply_text("📭 Новости закончились!")
            return await self.show_main_menu(update, context)
        
        news_item = self.news_data[self.current_news_index[user_id]]
        
        # Создаем сообщение с новостью
        message_text = f"📰 {news_item['title']}\n\n"
        if news_item['rubric']:
            message_text += f"🏷️ Рубрика: {news_item['rubric']}\n"
        if news_item['date']:
            message_text += f"📅 Дата: {news_item['date']}\n"
        if news_item['link']:
            message_text += f"🔗 Подробнее: {news_item['link']}"
        
        # Клавиатура для навигации
        keyboard = [
            [KeyboardButton("➡️ Следующая новость")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем сообщение
        if news_item.get('image_url'):
            try:
                await update.message.reply_photo(
                    photo=news_item['image_url'],
                    caption=message_text,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")
                await update.message.reply_text(
                    message_text,
                    reply_markup=reply_markup
                )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup
            )

    async def next_news(self, update: Update, context: CallbackContext) -> int:
        """Следующая новость"""
        user_id = update.message.from_user.id
        
        # Увеличиваем индекс
        self.current_news_index[user_id] += 1
        
        # Показываем следующую новость
        await self.show_current_news(update, context, user_id)
        
        return VIEWING_NEWS

    async def show_club_news_menu(self, update: Update, context: CallbackContext) -> int:
        """Меню выбора клуба"""
        keyboard = [
            [KeyboardButton("Реал Мадрид"), KeyboardButton("Барселона")],
            [KeyboardButton("Манчестер Юнайтед"), KeyboardButton("Челси")],
            [KeyboardButton("Бавария"), KeyboardButton("Ювентус")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите клуб:",
            reply_markup=reply_markup
        )
        
        return VIEWING_CLUB_NEWS

    async def show_club_news(self, update: Update, context: CallbackContext) -> int:
        """Показ новостей по клубу"""
        club_name = update.message.text
        user_id = update.message.from_user.id
        
        # Фильтруем новости по клубу (простой поиск по заголовку)
        club_news = [
            news for news in self.news_data 
            if club_name.lower() in news['title'].lower()
        ]
        
        if not club_news:
            await update.message.reply_text(
                f"❌ Новости по клубу '{club_name}' не найдены.\n"
                "Попробуйте другой клуб."
            )
            return await self.show_club_news_menu(update, context)
        
        # Сохраняем отфильтрованные новости для пользователя
        context.user_data['club_news'] = club_news
        context.user_data['club_news_index'] = 0
        
        # Показываем первую новость
        await self.show_current_club_news(update, context, user_id, club_name)
        
        return VIEWING_NEWS

    async def show_current_club_news(self, update: Update, context: CallbackContext, user_id: int, club_name: str):
        """Показ текущей новости клуба"""
        club_news = context.user_data.get('club_news', [])
        current_index = context.user_data.get('club_news_index', 0)
        
        if current_index >= len(club_news):
            await update.message.reply_text(f"📭 Новости по клубу '{club_name}' закончились!")
            return await self.show_main_menu(update, context)
        
        news_item = club_news[current_index]
        
        # Создаем сообщение с новостью
        message_text = f"🏆 {club_name}\n📰 {news_item['title']}\n\n"
        if news_item['rubric']:
            message_text += f"🏷️ Рубрика: {news_item['rubric']}\n"
        if news_item['date']:
            message_text += f"📅 Дата: {news_item['date']}\n"
        if news_item['link']:
            message_text += f"🔗 Подробнее: {news_item['link']}"
        
        # Клавиатура для навигации
        keyboard = [
            [KeyboardButton("➡️ Следующая новость")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем сообщение
        if news_item.get('image_url'):
            try:
                await update.message.reply_photo(
                    photo=news_item['image_url'],
                    caption=message_text,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")
                await update.message.reply_text(
                    message_text,
                    reply_markup=reply_markup
                )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup
            )

    async def handle_message(self, update: Update, context: CallbackContext) -> int:
        """Обработка текстовых сообщений"""
        text = update.message.text
        user_id = update.message.from_user.id
        
        if text == "📰 Смотреть все новости":
            return await self.show_all_news(update, context)
        
        elif text == "🏆 Смотреть новости по конкретному клубу":
            return await self.show_club_news_menu(update, context)
        
        elif text == "➡️ Следующая новость":
            # Проверяем, просматриваем ли мы новости клуба или все новости
            if 'club_news' in context.user_data:
                context.user_data['club_news_index'] += 1
                club_name = next((club for club in [
                    "Реал Мадрид", "Барселона", "Манчестер Юнайтед", 
                    "Челси", "Бавария", "Ювентус"
                ] if club in context.user_data.get('last_club', '')), 'клуба')
                return await self.show_current_club_news(update, context, user_id, club_name)
            else:
                return await self.next_news(update, context)
        
        elif text == "🏠 Главное меню":
            return await self.show_main_menu(update, context)
        
        elif text in ["Реал Мадрид", "Барселона", "Манчестер Юнайтед", "Челси", "Бавария", "Ювентус"]:
            context.user_data['last_club'] = text
            return await self.show_club_news(update, context)
        
        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки для навигации.")
            return await self.show_main_menu(update, context)

    async def error_handler(self, update: Update, context: CallbackContext) -> None:
        """Обработка ошибок"""
        logger.error(f"Ошибка: {context.error}", exc_info=context.error)
        
        if update and update.message:
            await update.message.reply_text(
                "❌ Произошла ошибка. Пожалуйста, попробуйте позже."
            )

    def run(self):
        """Запуск бота"""
        application = Application.builder().token(self.token).build()
        
        # Conversation handler для управления состояниями
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
                ],
                VIEWING_NEWS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
                ],
                VIEWING_CLUB_NEWS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
                ],
            },
            fallbacks=[CommandHandler('start', self.start)],
        )
        
        application.add_handler(conv_handler)
        application.add_error_handler(self.error_handler)
        
        print("Бот запущен...")
        application.run_polling()

# Запуск бота
if __name__ == "__main__":
    # Замените 'YOUR_BOT_TOKEN' на токен вашего бота
    BOT_TOKEN = "YOUR_BOT_TOKEN"
    
    bot = FootballNewsBot(BOT_TOKEN)
    bot.run()