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

TOKEN = "7804678382:AAGQ31AZzpaSoBQSMT-gN-fcNTknbcEEB3M"
ADMIN_ID = 911657126  # Убедитесь, что это ваш правильный Telegram ID

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
    # Отправляем текстовое сообщение с кнопкой
    await message.answer("❤️Приветик! Здесь можешь заказать свой мерч❤️", reply_markup=buy_button)
    # Отправляем картинку по ссылке для /start
    await bot.send_photo(
        chat_id=message.chat.id, 
        photo="https://github.com/kmstok/-chernikame_bot/blob/main/images/glaza.JPG?raw=true"
    )

# Обработчик нажатия "Купить"
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

# Обработчик данных с улучшенной проверкой состояния
@router.message(F.text)
async def process_order(message: types.Message, state: FSMContext):
    logger.debug(f"✅ Вошел в обработчик process_order для пользователя {message.from_user.id}")
    logger.debug(f"✅ Получено сообщение от пользователя: {message.text}")

    # Получаем состояние FSM для пользователя
    current_state = await state.get_state()
    logger.debug(f"✅ Текущее состояние перед обработкой для пользователя {message.from_user.id}: {current_state}")

    if current_state == 'OrderForm:user_data':
        logger.debug(f"✅ Обрабатываем данные от пользователя {message.from_user.id}")
        # Разделяем данные по строкам
        lines = message.text.split("\n")
        lines = [line.strip() for line in lines if line.strip()]

        logger.debug(f"✅ Разделенные строки от пользователя {message.from_user.id}: {lines}")

        if len(lines) < 4:
            logger.error(f"❌ Ошибка: Недостаточно данных от пользователя {message.from_user.id}.")
            await message.answer("❌ Пожалуйста, отправьте 4 строки с вашими данными (ФИО, телефон, адрес, email).")
            return

        full_name, phone, address, email = lines[:4]
        logger.debug(f"✅ Получены данные от пользователя {message.from_user.id} - ФИО: {full_name}, Телефон: {phone}, Адрес: {address}, Email: {email}")

        # Проверка данных
        valid, error_message = validate_data(full_name, phone, address, email)
        if not valid:
            logger.error(f"❌ Ошибка при проверке данных от пользователя {message.from_user.id}: {error_message}")
            await message.answer(error_message)
            return

        logger.debug("✅ Все данные прошли проверку. Отправляю информацию админу.")

        # Формирование информации о заказе
        order_info = (
            f"📦 *Новый заказ:*\n"
            f"👤 *ФИО:* {full_name}\n"
            f"📞 *Телефон:* {phone}\n"
            f"🏠 *Адрес CDEK:* {address}\n"
            f"✉ *Email:* {email}"
        )

        # Отправка заказа админу
        try:
            await bot.send_message(ADMIN_ID, order_info, parse_mode="Markdown")
            logger.debug(f"✅ Информация отправлена админу для пользователя {message.from_user.id}.")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке данных админу для пользователя {message.from_user.id}: {e}")
            await message.answer("❌ Произошла ошибка при отправке данных. Попробуйте позже.")
            return

        # Отправляем подтверждающее сообщение пользователю
        await message.answer(
            "🍃Готово! Поздравляю с покупкой🍃\n\n"
            "Мне нужно некоторое время, чтобы рассчитать стоимость отправки. Скоро свяжусь с тобой для оплаты и уточнения деталей ❤️"
        )
        # Отправляем картинку для подтверждения заказа
        await bot.send_photo(
            chat_id=message.chat.id, 
            photo="https://github.com/kmstok/-chernikame_bot/blob/main/images/palec.JPG?raw=true"
        )

        await state.clear()  # Очистка состояния после завершения
    else:
        logger.error(f"❌ Ошибка: Получено сообщение от пользователя {message.from_user.id}, но состояние не соответствует ожидаемому.")
        await message.answer("❌ Произошла ошибка с состоянием. Пожалуйста, начни заново.")

# Функция для проверки данных
def validate_data(full_name, phone, address, email):
    # Убираем все нецифровые символы из телефона
    phone = re.sub(r'\D', '', phone)

    # Проверка корректности email
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_pattern, email):
        return False, "❌ Некорректный email. Введите правильный адрес почты."

    return True, None

# Запуск бота
async def main():
    try:
        logger.debug("✅ Бот запущен...")
        dp.include_router(router)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")

if __name__ == '__main__':
    asyncio.run(main())
