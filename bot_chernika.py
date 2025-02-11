import loggimport logging
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
from aiogram.utils.markdown import escape_md  # Используем встроенный экранирующий метод

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

# === Функция для разбора данных пользователя ===
def parse_user_data(text: str):
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) < 4:
        return False, "Недостаточно данных. Укажите ФИО, телефон, адрес и email."

    email = None
    phone = None
    others = []
    for line in lines:
        if "@" in line and re.match(email_pattern, line):
            email = line
        elif len(re.sub(r'\D', '', line)) in [11, 12]:
            phone = line
        else:
            others.append(line)

    if len(others) >= 2:
        if ',' in others[0]:
            address, full_name = others[0], others[1]
        elif ',' in others[1]:
            address, full_name = others[1], others[0]
        else:
            full_name, address = (others[0], others[1]) if len(others[0].split()) <= len(others[1].split()) else (others[1], others[0])
    else:
        return False, "Не удалось определить ФИО и адрес. Проверьте ввод данных."

    if not (email and phone and full_name and address):
        return False, "Не удалось определить все данные. Убедитесь, что указали ФИО, телефон, адрес и email."

    return True, {"full_name": full_name, "phone": phone, "address": address, "email": email}

# === Функция проверки данных ===
def validate_data(full_name: str, phone: str, address: str, email: str):
    phone_digits = re.sub(r'\D', '', phone)
    if len(phone_digits) not in [11, 12]:
        return False, "❌ Некорректный номер телефона."

    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_pattern, email):
        return False, "❌ Некорректный email."

    return True, None

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
        "Введите:\n1. ФИО\n2. Телефон\n3. Адрес\n4. Email",
        reply_markup=types.ReplyKeyboardRemove()
    )

# === Обработчик данных ===
@router.message(F.text)
async def process_order(message: types.Message, state: FSMContext):
    logger.debug(f"✅ Обработка сообщения {message.from_user.id}")

    current_state = await state.get_state()
    if current_state == OrderForm.user_data.state:
        success, result = parse_user_data(message.text)
        if not success:
            await message.answer(result)
            return

        full_name = escape_md(result["full_name"])
        phone = escape_md(result["phone"])
        address = escape_md(result["address"])
        email = escape_md(result["email"])

        valid, error_message = validate_data(full_name, phone, address, email)
        if not valid:
            await message.answer(error_message)
            return

        order_info = (
            f"📦 *Новый заказ:*\n"
            f"👤 *ФИО:* {full_name}\n"
            f"📞 *Телефон:* {phone}\n"
            f"🏠 *Адрес:* {address}\n"
            f"✉ *Email:* {email}"
        )

        try:
            await bot.send_message(ADMIN_ID, order_info, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки админу: {e}")
            await message.answer("❌ Ошибка при передаче заказа админу.")
            return

        confirmation_caption = "🍃Готово! Поздравляю с покупкой🍃"
        try:
            await bot.send_photo(message.chat.id, PALEC_URL, caption=confirmation_caption)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            await message.answer("❌ Ошибка при отправке фото.")

        await state.clear()
    else:
        await message.answer("❌ Ошибка. Начните заново.")

# === Команда /help ===
@router.message(F.text == "/help")
async def help_command(message: types.Message):
    await message.answer("Этот бот помогает заказать мерч. Нажмите 'Купить' и следуйте инструкциям.")

# === Основной запуск ===
async def main():
    try:
        dp.include_router(router)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
