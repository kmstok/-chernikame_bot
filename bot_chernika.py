import logging
import asyncio
import re
import os
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.text_decorations import markdown_decoration  # Исправленный импорт

# === Flask веб-сервер для Render.com ===
app = Flask(__name__)

@app.route('/')
def index():
    return "Бот работает!"

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Ошибка сервера: {e}")
    return "Ошибка сервера", 500

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# === Конфигурация логирования ===
logging.basicConfig(level=logging.DEBUG, filename="bot_log.log", filemode="w")
logger = logging.getLogger(__name__)

# === Хардкод токена и ADMIN_ID ===
TOKEN = "7804678382:AAGQ31AZzpaSoBQSMT-gN-fcNTknbcEEB3M"
ADMIN_ID = 911657126

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher()
dp["bot"] = bot  # Связываем бота с диспетчером
router = Router()

# === Определяем состояния с помощью FSM ===
class OrderForm(StatesGroup):
    user_data = State()

# === Кнопка "Купить" ===
buy_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Купить")]],
    resize_keyboard=True
)

# === Новые ссылки на изображения ===
GLAZA_URL = "https://raw.githubusercontent.com/kmstok/-chernikame_bot/main/images/glaza.JPG"
PALEC_URL = "https://raw.githubusercontent.com/kmstok/-chernikame_bot/main/images/palec.JPG"

# === Функция экранирования Markdown ===
def escape_md(text: str) -> str:
    return markdown_decoration.quote(text)  # Новый метод экранирования

# === Команда /start ===
@router.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик /start")
    caption_text = "❤️Приветик! Здесь можешь заказать свой мерч❤️"
    try:
        await bot.send_photo(message.chat.id, GLAZA_URL, caption=caption_text, reply_markup=buy_button)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await message.answer("❌ Не удалось отправить фото.")

# === Обработчик кнопки "Купить" ===
@router.message(F.text == "Купить")
async def ask_order_data(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик 'Купить'")
    await state.set_state(OrderForm.user_data)
    await message.answer(
        "Теперь укажи свои данные для отправки:\n"
        "1. ФИО\n"
        "2. Номер телефона\n"
        "3. Адрес пункта СДЭК\n"
        "4. Электронная почта (туда придет трек-номер отслеживания)",
        reply_markup=types.ReplyKeyboardRemove()
    )

# === Основной запуск ===
async def main():
    try:
        dp.include_router(router)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    
    loop = asyncio.new_event_loop()  # Новый event loop
    asyncio.set_event_loop(loop)  # Устанавливаем его как текущий
    
    loop.run_until_complete(main())  # Запускаем бота
