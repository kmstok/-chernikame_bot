import os
import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Настройка логирования в файл
logging.basicConfig(level=logging.DEBUG, filename="bot_log.log", filemode="w")
logger = logging.getLogger()

TOKEN = "YOUR_BOT_TOKEN"  # Замените на ваш токен
ADMIN_ID = YOUR_ADMIN_ID  # Ваш Telegram ID

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Определяем состояние
class OrderForm(StatesGroup):
    user_data = State()

# Кнопка "Купить"
buy_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Купить")]],
    resize_keyboard=True
)

# Команда /start
@router.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик /start")
    await message.answer("❤️Приветик! Здесь можешь заказать свой мерч❤️", reply_markup=buy_button)

# Обработчик нажатия "Купить"
@router.message(F.text == "Купить")
async def ask_order_data(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик 'Купить'")
    await state.set_state(OrderForm.user_data)
    await message.answer(
        "Теперь укажи свои данные для отправки:\n"
        "1. ФИО\n"
        "2. Номер телефона\n"
        "3. Адрес пункта СДЭК\n"
        "4. Электронная почта (туда придет трек-номер отслеживания)\n\n"
        "Пример:\nИванов Иван Иванович\n+79991234567\nМосква, ул. Ленина, д. 5\nexample@mail.com",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обработчик данных с улучшенной проверкой состояния
@router.message(F.text)
async def process_order(message: types.Message, state: FSMContext):
    logger.debug(f"✅ Вошел в обработчик process_order для пользователя {message.from_user.id}")
    lines = message.text.split("\n")
    lines = [line.strip() for line in lines if line.strip()]

    if len(lines) < 4:
        await message.answer("❌ Пожалуйста, отправьте 4 строки с вашими данными (ФИО, телефон, адрес, email).")
        return

    full_name, phone, address, email = lines[:4]
    valid, error_message = validate_data(full_name, phone, address, email)
    if not valid:
        await message.answer(error_message)
        return

    order_info = (
        f"📦 *Новый заказ:*\n"
        f"👤 *ФИО:* {full_name}\n"
        f"📞 *Телефон:* {phone}\n"
        f"🏠 *Адрес CDEK:* {address}\n"
        f"✉ *Email:* {email}"
    )

    try:
        await bot.send_message(ADMIN_ID, order_info, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке данных админу: {e}")
        await message.answer("❌ Произошла ошибка при отправке данных. Попробуйте позже.")
        return

    # Отправляем картинку
    await bot.send_photo(chat_id=message.chat.id, photo="https://imgur.com/a/yTrx5vV")
    await bot.send_photo(chat_id=message.chat.id, photo="https://imgur.com/a/GgqvdxJ")

    # Подтверждаем пользователю
    await message.answer("🍃Готово! Поздравляю с покупкой🍃\n\n"
                         "Мне нужно некоторое время, чтобы рассчитать стоимость отправки. Скоро свяжусь с тобой для оплаты и уточнения деталей ❤️")
    await state.clear()  # Очистка состояния после завершения

# Функция для проверки данных
def validate_data(full_name, phone, address, email):
    phone = re.sub(r'\D', '', phone)

    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_pattern, email):
        return False, "❌ Некорректный email. Введите правильный адрес почты."

    return True, None

# Запуск бота
async def main():
    try:
        logger.debug("✅ Бот запущен...")
        dp.include_router(router)
        # Используем переменную окружения PORT для привязки
        port = int(os.environ.get("PORT", 5000))  # По умолчанию порт 5000, если не указан
        logger.debug(f"Привязываемся к порту {port}")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")

if __name__ == '__main__':
    asyncio.run(main())
