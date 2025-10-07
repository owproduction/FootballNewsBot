import os
import json
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
import asyncio

# Импорт вашего парсера
from scrap import SimpleSportboxScraper
from scrap import main as scrap_main

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния FSM
class UserStates(StatesGroup):
    main_menu = State()
    viewing_news = State()
    viewing_club_news = State()
    selecting_club = State()

class FootballNewsBot:
    def __init__(self, token: str):
        self.token = token
        self.scraper = SimpleSportboxScraper()
        self.news_data = []
        self.current_news_index = {}
        self.is_parsing = False  # Флаг для отслеживания парсинга
        
        # Инициализация aiogram
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.router = Router()
        self.dp.include_router(self.router)
        
        # Регистрация обработчиков
        self.register_handlers()

    def register_handlers(self):
        """Регистрация всех обработчиков"""
        # Команда /start
        self.router.message.register(self.start_handler, Command("start"))
        
        # Главное меню
        self.router.message.register(self.main_menu_handler, StateFilter(UserStates.main_menu))
        
        # Просмотр новостей
        self.router.message.register(self.news_handler, StateFilter(UserStates.viewing_news))
        
        # Выбор клуба
        self.router.message.register(self.club_selection_handler, StateFilter(UserStates.selecting_club))

    async def get_news_data(self):
        """Получение данных новостей с обработкой асинхронности"""
        if self.is_parsing:
            return self.news_data
            
        self.is_parsing = True
        try:
            # Запускаем парсинг в отдельном потоке, так как он синхронный
            loop = asyncio.get_event_loop()
            news = await loop.run_in_executor(None, scrap_main)
            
            # Фильтруем пустые новости
            if news:
                self.news_data = [item for item in news if item.get('title')]
                logger.info(f"Успешно загружено {len(self.news_data)} новостей")
            else:
                logger.warning("Парсер вернул пустой список новостей")
                self.news_data = []
                
            return self.news_data
        except Exception as e:
            logger.error(f"Ошибка при парсинге новостей: {e}")
            return []
        finally:
            self.is_parsing = False

    async def start_handler(self, message: Message, state: FSMContext):
        """Начало работы с ботом"""
        user = message.from_user
        logger.info(f"Пользователь {user.first_name} начал работу с ботом")
        
        # Инициализация состояния пользователя
        user_id = user.id
        self.current_news_index[user_id] = 0
        
        # Показываем сообщение о загрузке
        loading_msg = await message.answer("🔄 Загружаю свежие новости...")
        
        # Загружаем новости
        news_data = await self.get_news_data()
        
        # Удаляем сообщение о загрузке
        await loading_msg.delete()
        
        if not news_data:
            await message.answer("❌ Не удалось загрузить новости. Попробуйте позже.")
            return
        
        # Клавиатура главного меню
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📰 Смотреть все новости")],
                [KeyboardButton(text="🏆 Смотреть новости по конкретному клубу")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "⚽ Добро пожаловать в футбольный новостной бот!\n"
            f"📊 Загружено {len(news_data)} свежих новостей!\n"
            "Выберите опцию:",
            reply_markup=keyboard
        )
        
        await state.set_state(UserStates.main_menu)

    async def main_menu_handler(self, message: Message, state: FSMContext):
        """Обработка главного меню"""
        text = message.text
        
        if text == "📰 Смотреть все новости":
            await self.show_all_news(message, state)
        
        elif text == "🏆 Смотреть новости по конкретному клубу":
            await self.show_club_selection_menu(message, state)

    async def show_all_news(self, message: Message, state: FSMContext):
        """Показ всех новостей"""
        user_id = message.from_user.id
        
        # Обновляем новости при каждом запросе
        news_data = await self.get_news_data()
        
        if not news_data:
            await message.answer("❌ Новости временно недоступны. Попробуйте позже.")
            return await self.show_main_menu(message, state)
        
        # Сбрасываем индекс для пользователя
        self.current_news_index[user_id] = 0
        
        # Показываем первую новость
        await self.show_current_news(message, state, user_id)
        
        await state.set_state(UserStates.viewing_news)

    async def show_current_news(self, message: Message, state: FSMContext, user_id: int):
        """Показ текущей новости"""
        if user_id not in self.current_news_index:
            self.current_news_index[user_id] = 0
            
        current_index = self.current_news_index[user_id]
        
        if current_index >= len(self.news_data):
            await message.answer("📭 Новости закончились!")
            return await self.show_main_menu(message, state)
        
        news_item = self.news_data[current_index]
        
        # Создаем сообщение с новостью
        message_text = f"📰 {news_item.get('title', 'Без заголовка')}\n\n"
        if news_item.get('rubric'):
            message_text += f"🏷️ Рубрика: {news_item['rubric']}\n"
        if news_item.get('date'):
            message_text += f"📅 Дата: {news_item['date']}\n"
        if news_item.get('link'):
            message_text += f"🔗 Подробнее: {news_item['link']}\n"
        
        message_text += f"\n📊 Новость {current_index + 1} из {len(self.news_data)}"
        
        # Клавиатура для навигации
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="➡️ Следующая новость")],
                [KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True
        )
        
        # Отправляем сообщение
        try:
            if news_item.get('image_url'):
                await message.answer_photo(
                    photo=news_item['image_url'],
                    caption=message_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            else:
                await message.answer(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Ошибка отправки новости: {e}")
            await message.answer(
                message_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )

    async def show_club_selection_menu(self, message: Message, state: FSMContext):
        """Меню выбора клуба"""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Реал Мадрид"), KeyboardButton(text="Барселона")],
                [KeyboardButton(text="Манчестер Юнайтед"), KeyboardButton(text="Челси")],
                [KeyboardButton(text="Бавария"), KeyboardButton(text="Ювентус")],
                [KeyboardButton(text="🔍 Другие клубы"), KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "Выберите клуб:",
            reply_markup=keyboard
        )
        
        await state.set_state(UserStates.selecting_club)

    async def club_selection_handler(self, message: Message, state: FSMContext):
        """Обработка выбора клуба"""
        text = message.text
        
        if text == "🏠 Главное меню":
            await self.show_main_menu(message, state)
            return
        
        if text == "🔍 Другие клубы":
            await message.answer("Введите название клуба:")
            return
        
        # Проверяем, что выбран один из клубов
        clubs = ["Реал Мадрид", "Барселона", "Манчестер Юнайтед", "Челси", "Бавария", "Ювентус"]
        if text in clubs:
            await self.show_club_news(message, state, text)
        else:
            # Пользователь ввел свой клуб
            await self.show_club_news(message, state, text)

    async def show_club_news(self, message: Message, state: FSMContext, club_name: str):
        """Показ новостей по клубу"""
        user_id = message.from_user.id
        
        # Обновляем новости
        news_data = await self.get_news_data()
        
        if not news_data:
            await message.answer("❌ Новости временно недоступны. Попробуйте позже.")
            return await self.show_main_menu(message, state)
        
        # Фильтруем новости по клубу (ищем в заголовке и рубрике)
        club_news = []
        for news in news_data:
            title = news.get('title', '').lower()
            rubric = news.get('rubric', '').lower()
            club_lower = club_name.lower()
            
            if (club_lower in title or 
                club_lower in rubric or
                any(word in title for word in club_lower.split())):
                club_news.append(news)
        
        logger.info(f"Найдено новостей для клуба '{club_name}': {len(club_news)}")
        
        if not club_news:
            await message.answer(
                f"❌ Новости по клубу '{club_name}' не найдены.\n"
                "Попробуйте другой клуб или посмотрите все новости."
            )
            return await self.show_club_selection_menu(message, state)
        
        # Сохраняем отфильтрованные новости в состоянии
        await state.update_data(
            club_news=club_news,
            club_news_index=0,
            current_club=club_name
        )
        
        # Показываем первую новость
        await self.show_current_club_news(message, state, user_id)
        
        await state.set_state(UserStates.viewing_news)

    async def show_current_club_news(self, message: Message, state: FSMContext, user_id: int):
        """Показ текущей новости клуба"""
        user_data = await state.get_data()
        club_news = user_data.get('club_news', [])
        current_index = user_data.get('club_news_index', 0)
        club_name = user_data.get('current_club', 'клубу')
        
        if current_index >= len(club_news):
            await message.answer(f"📭 Новости по клубу '{club_name}' закончились!")
            return await self.show_main_menu(message, state)
        
        news_item = club_news[current_index]
        
        # Создаем сообщение с новостью
        message_text = f"🏆 {club_name}\n📰 {news_item.get('title', 'Без заголовка')}\n\n"
        if news_item.get('rubric'):
            message_text += f"🏷️ Рубрика: {news_item['rubric']}\n"
        if news_item.get('date'):
            message_text += f"📅 Дата: {news_item['date']}\n"
        if news_item.get('link'):
            message_text += f"🔗 Подробнее: {news_item['link']}\n"
        
        message_text += f"\n📊 Новость {current_index + 1} из {len(club_news)}"
        
        # Клавиатура для навигации
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="➡️ Следующая новость")],
                [KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True
        )
        
        # Отправляем сообщение
        try:
            if news_item.get('image_url'):
                await message.answer_photo(
                    photo=news_item['image_url'],
                    caption=message_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            else:
                await message.answer(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Ошибка отправки новости клуба: {e}")
            await message.answer(
                message_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )

    async def news_handler(self, message: Message, state: FSMContext):
        """Обработка навигации по новостям"""
        text = message.text
        user_id = message.from_user.id
        
        if text == "➡️ Следующая новость":
            user_data = await state.get_data()
            
            # Проверяем, просматриваем ли мы новости клуба или все новости
            if 'club_news' in user_data:
                # Новости клуба
                current_index = user_data.get('club_news_index', 0)
                await state.update_data(club_news_index=current_index + 1)
                await self.show_current_club_news(message, state, user_id)
            else:
                # Все новости
                self.current_news_index[user_id] += 1
                await self.show_current_news(message, state, user_id)
        
        elif text == "🏠 Главное меню":
            await self.show_main_menu(message, state)

    async def show_main_menu(self, message: Message, state: FSMContext):
        """Показ главного меню"""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📰 Смотреть все новости")],
                [KeyboardButton(text="🏆 Смотреть новости по конкретному клубу")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "Главное меню:",
            reply_markup=keyboard
        )
        
        await state.set_state(UserStates.main_menu)

    async def run(self):
        """Запуск бота"""
        # Удаляем вебхук (на всякий случай)
        await self.bot.delete_webhook(drop_pending_updates=True)
        
        print("Бот запущен...")
        
        # Запускаем поллинг
        await self.dp.start_polling(self.bot)

# Запуск бота
async def main():
    # Замените 'YOUR_BOT_TOKEN' на токен вашего бота
    BOT_TOKEN = "8218894092:AAGFGRvI0C-OczsJMcOFej8f9zM6AXukqL4"
    
    bot = FootballNewsBot(BOT_TOKEN)
    await bot.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())