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

# === Flask веб-сервер для Render.com ===
app = Flask(__name__)

@app.route('/')
def index():
    return "Бот работает!"

def run_web_server():
    # Render задаёт переменную окружения PORT, если её нет — используем порт 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# === Конфигурация логирования ===
logging.basicConfig(level=logging.DEBUG, filename="bot_log.log", filemode="w")
logger = logging.getLogger(__name__)

# === Хардкод токена и ADMIN_ID (временно) ===
TOKEN = "7804678382:AAGQ31AZzpaSoBQSMT-gN-fcNTknbcEEB3M"
ADMIN_ID = 911657126

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# === Определяем состояния с помощью FSM ===
class OrderForm(StatesGroup):
    user_data = State()

# === Кнопка "Купить" ===
buy_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Купить")]],
    resize_keyboard=True
)

# === Функция экранирования Markdown-символов ===
def escape_markdown(text: str) -> str:
    escape_chars = r'\*_`['
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text

# === Команда /start – отправляем фото и текст одним сообщением ===
@router.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик /start")
    caption_text = "❤️Приветик! Здесь можешь заказать свой мерч❤️"
    await bot.send_photo(
        chat_id=message.chat.id,
        photo="https://github.com/kmstok/-chernikame_bot/blob/main/images/glaza.JPG?raw=true",
        caption=caption_text,
        reply_markup=buy_button
    )

# === Обработчик нажатия "Купить" ===
@router.message(F.text == "Купить")
async def ask_order_data(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик 'Купить'")
    await state.set_state(OrderForm.user_data)
    logger.debug("✅ Состояние установлено на OrderForm.user_data")
    await message.answer(
        "Теперь укажи свои данные для отправки:\n"
        "1. ФИО\n"
        "2. Номер телефона\n"
        "3. Адрес пункта СДЭК\n"
        "4. Электронная почта (туда придет трек-номер отслеживания)\n\n"
        "Пример:\nИванов Иван Иванович\n+79991234567\nМосква, ул. Ленина, д. 5\nexample@mail.com",
        reply_markup=types.ReplyKeyboardRemove()
    )

# === Обработчик данных с проверкой состояния ===
@router.message(F.text)
async def process_order(message: types.Message, state: FSMContext):
    logger.debug(f"✅ Вошел в обработчик process_order для пользователя {message.from_user.id}")
    logger.debug(f"✅ Получено сообщение от пользователя: {message.text}")

    # Получаем текущее состояние FSM для пользователя
    current_state = await state.get_state()
    logger.debug(f"✅ Текущее состояние перед обработкой для пользователя {message.from_user.id}: {current_state}")

    if current_state == 'OrderForm:user_data':
        logger.debug(f"✅ Обрабатываем данные от пользователя {message.from_user.id}")
        # Разделяем данные по строкам и убираем лишние пробелы
        lines = message.text.split("\n")
        lines = [line.strip() for line in lines if line.strip()]

        logger.debug(f"✅ Разделенные строки от пользователя {message.from_user.id}: {lines}")

        if len(lines) < 4:
            logger.error(f"❌ Ошибка: Недостаточно данных от пользователя {message.from_user.id}.")
            await message.answer("❌ Пожалуйста, отправьте 4 строки с вашими данными (ФИО, телефон, адрес, email).")
            return

        full_name, phone, address, email = lines[:4]

        # Экранируем данные для безопасного вывода в Markdown
        full_name = escape_markdown(full_name)
        phone = escape_markdown(phone)
        address = escape_markdown(address)
        email = escape_markdown(email)

        logger.debug(f"✅ Получены данные от пользователя {message.from_user.id} - ФИО: {full_name}, Телефон: {phone}, Адрес: {address}, Email: {email}")

        # Проверка корректности данных
        valid, error_message = validate_data(full_name, phone, address, email)
        if not valid:
            logger.error(f"❌ Ошибка при проверке данных от пользователя {message.from_user.id}: {error_message}")
            await message.answer(error_message)
            return

        logger.debug("✅ Все данные прошли проверку. Отправляю информацию админу.")

        # Формирование информации о заказе для администратора
        order_info = (
            f"📦 *Новый заказ:*\n"
            f"👤 *ФИО:* {full_name}\n"
            f"📞 *Телефон:* {phone}\n"
            f"🏠 *Адрес CDEK:* {address}\n"
            f"✉ *Email:* {email}"
        )

        # Отправляем заказ админу (с использованием Markdown)
        try:
            await bot.send_message(ADMIN_ID, order_info, parse_mode="Markdown")
            logger.debug(f"✅ Информация отправлена админу для пользователя {message.from_user.id}.")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке данных админу для пользователя {message.from_user.id}: {e}")
            await message.answer("❌ Произошла ошибка при отправке данных. Попробуйте позже.")
            return

        # Отправляем подтверждающее сообщение пользователю с фото и текстом в одном сообщении
        confirmation_caption = (
            "🍃Готово! Поздравляю с покупкой🍃\n\n"
            "Мне нужно некоторое время, чтобы рассчитать стоимость отправки. Скоро свяжусь с тобой для оплаты и уточнения деталей ❤️"
        )
        await bot.send_photo(
            chat_id=message.chat.id,
            photo="https://github.com/kmstok/-chernikame_bot/blob/main/images/palec.JPG?raw=true",
            caption=confirmation_caption
        )

        await state.clear()  # Очистка состояния после завершения
    else:
        logger.error(f"❌ Ошибка: Получено сообщение от пользователя {message.from_user.id}, но состояние не соответствует ожидаемому.")
        await message.answer("❌ Произошла ошибка с состоянием. Пожалуйста, начни заново.")

# === Функция для проверки данных ===
def validate_data(full_name: str, phone: str, address: str, email: str) -> (bool, str):
    # Удаляем все нецифровые символы из номера телефона
    phone_digits = re.sub(r'\D', '', phone)
    if len(phone_digits) < 10:
        return False, "❌ Некорректный номер телефона. Убедитесь, что указали номер полностью."
    # Проверка корректности email с помощью регулярного выражения
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_pattern, email):
        return False, "❌ Некорректный email. Введите правильный адрес почты."
    return True, None

# === Основная функция запуска бота ===
async def main():
    try:
        logger.debug("✅ Бот запущен...")
        dp.include_router(router)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")

if __name__ == '__main__':
    # Запускаем веб-сервер в отдельном потоке, чтобы Render обнаружил открытый порт
    threading.Thread(target=run_web_server, daemon=True).start()
    # Запускаем бота
    asyncio.run(main())
