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

# === Функция экранирования специальных символов для Markdown ===
def escape_markdown(text: str) -> str:
    escape_chars = r'\*_`['
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text

# === Новые ссылки на изображения (используем raw.githubusercontent.com) ===
GLAZA_URL = "https://raw.githubusercontent.com/kmstok/-chernikame_bot/main/images/glaza.JPG"
PALEC_URL = "https://raw.githubusercontent.com/kmstok/-chernikame_bot/main/images/palec.JPG"

# === Функция для разбора данных пользователя (без привязки к порядку ввода) ===
def parse_user_data(text: str):
    """
    Пытаемся определить данные пользователя по строкам.
    Ожидается, что в сообщении будут присутствовать:
      - Email (строка, содержащая символ "@")
      - Телефон (строка, в которой после удаления нецифровых символов остаётся 11 или 12 цифр)
      - Остальные две строки: одну считаем ФИО, другую – адрес.
    Если встречается запятая, то с высокой вероятностью это адрес.
    """
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) < 4:
        return False, "Недостаточно данных. Укажите ФИО, телефон, адрес и email."

    email = None
    phone = None
    others = []
    for line in lines:
        # Если строка содержит @ и удовлетворяет шаблону email, то это email
        if "@" in line and re.match(email_pattern, line):
            email = line
        # Если после удаления всего, кроме цифр, остаётся 11 или 12 цифр, считаем, что это телефон
        elif len(re.sub(r'\D', '', line)) in [11, 12]:
            phone = line
        else:
            others.append(line)
    # Для остальных двух строк попробуем определить: если есть запятая – скорее всего это адрес
    full_name = None
    address = None
    if len(others) >= 2:
        if ',' in others[0]:
            address = others[0]
            full_name = others[1]
        elif ',' in others[1]:
            address = others[1]
            full_name = others[0]
        else:
            if len(others[0].split()) <= len(others[1].split()):
                full_name = others[0]
                address = others[1]
            else:
                full_name = others[1]
                address = others[0]
    else:
        return False, "Не удалось определить ФИО и адрес. Проверьте ввод данных."

    if not (email and phone and full_name and address):
        return False, "Не удалось определить все данные. Убедитесь, что указали ФИО, телефон, адрес и email."

    return True, {"full_name": full_name, "phone": phone, "address": address, "email": email}

# === Функция для проверки корректности данных ===
def validate_data(full_name: str, phone: str, address: str, email: str) -> (bool, str):
    # Проверка номера телефона: после удаления нецифровых символов должно быть 11 или 12 цифр
    phone_digits = re.sub(r'\D', '', phone)
    if len(phone_digits) not in [11, 12]:
        return False, "❌ Некорректный номер телефона. Укажите корректный номер (11 или 12 цифр)."
    # Проверка корректности email с помощью регулярного выражения
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_pattern, email):
        return False, "❌ Некорректный email. Введите правильный адрес почты."
    return True, None

# === Команда /start – отправляем фото и текст одним сообщением ===
@router.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик /start")
    caption_text = "❤️Приветик! Здесь можешь заказать свой мерч❤️"
    try:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=GLAZA_URL,
            caption=caption_text,
            reply_markup=buy_button
        )
        logger.debug("✅ Фото для /start отправлено успешно")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке фото для /start: {e}")
        await message.answer("❌ Не удалось отправить фото. Попробуйте позже.")

# === Обработчик нажатия "Купить" ===
@router.message(F.text == "Купить")
async def ask_order_data(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик 'Купить'")
    await state.set_state(OrderForm.user_data)
    logger.debug("✅ Состояние установлено на OrderForm.user_data")
    # Восстанавливаем исходный текст без примера
    await message.answer(
        "Теперь укажи свои данные для отправки:\n"
        "1. ФИО\n"
        "2. Номер телефона\n"
        "3. Адрес пункта СДЭК\n"
        "4. Электронная почта (туда придет трек-номер отслеживания)",
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
        success, result = parse_user_data(message.text)
        if not success:
            logger.error(f"❌ Ошибка при разборе данных для пользователя {message.from_user.id}: {result}")
            await message.answer(result)
            return

        # Извлекаем разобранные данные
        full_name = escape_markdown(result["full_name"])
        phone = escape_markdown(result["phone"])
        address = escape_markdown(result["address"])
        email = escape_markdown(result["email"])

        logger.debug(f"✅ Разобраны данные для пользователя {message.from_user.id} - ФИО: {full_name}, Телефон: {phone}, Адрес: {address}, Email: {email}")

        # Проверка корректности данных
        valid, error_message = validate_data(full_name, phone, address, email)
        if not valid:
            logger.error(f"❌ Ошибка при валидации данных для пользователя {message.from_user.id}: {error_message}")
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

        # Отправляем подтверждающее сообщение пользователю (текст и фото в одном сообщении)
        confirmation_caption = (
            "🍃Готово! Поздравляю с покупкой🍃\n\n"
            "Мне нужно некоторое время, чтобы рассчитать стоимость отправки. Скоро свяжусь с тобой для оплаты и уточнения деталей ❤️"
        )
        try:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=PALEC_URL,
                caption=confirmation_caption
            )
            logger.debug("✅ Фото подтверждения заказа отправлено успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке фото подтверждения заказа: {e}")
            await message.answer("❌ Не удалось отправить фото подтверждения заказа.")
        
        await state.clear()  # Очистка состояния после завершения
    else:
        logger.error(f"❌ Ошибка: Получено сообщение от пользователя {message.from_user.id}, но состояние не соответствует ожидаемому.")
        await message.answer("❌ Произошла ошибка с состоянием. Пожалуйста, начни заново.")

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
