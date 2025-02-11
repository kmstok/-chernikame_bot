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
    logger.debug("✅ Вошел в обработчик /start")  # Логирование входа в обработчик
    await message.answer("Привет! Давай вместе оформим заказ?", reply_markup=buy_button)

# Обработчик нажатия "Купить"
@router.message(F.text == "Купить")
async def ask_order_data(message: types.Message, state: FSMContext):
    logger.debug("✅ Вошел в обработчик 'Купить'")  # Логирование перехода в обработчик
    await state.set_state(OrderForm.user_data)
    logger.debug("✅ Состояние установлено на OrderForm.user_data")  # Лог состояния
    await message.answer(
        "Отлично!\nЯ отправляю посылки по всей России (где есть CDEK).\n\n"
        "Укажи, пожалуйста, свои данные для доставки в ОДНОМ СООБЩЕНИИ:\n"
        "1. ФИО\n2. Номер телефона\n3. Адрес пункта CDEK\n4. Электронная почта (для получения трек-номера)\n\n"
        "Пример:\nИванов Иван Иванович\n+79991234567\nМосква, ул. Ленина, д. 5\nexample@mail.com",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обработчик данных с улучшенной проверкой состояния
@router.message(F.text)
async def process_order(message: types.Message, state: FSMContext):
    logger.debug(f"✅ Вошел в обработчик process_order для пользователя {message.from_user.id}")  # Логирование ID пользователя
    logger.debug(f"✅ Получено сообщение от пользователя: {message.text}")  # Логирование полученного текста

    # Получаем состояние FSM для пользователя
    current_state = await state.get_state()
    logger.debug(f"✅ Текущее состояние перед обработкой для пользователя {message.from_user.id}: {current_state}")  # Лог состояния

    if current_state == 'OrderForm:user_data':
        logger.debug(f"✅ Обрабатываем данные от пользователя {message.from_user.id}")
        # Разделяем данные на строки
        lines = message.text.split("\n")  # Разделяем данные только по новой строке
        lines = [line.strip() for line in lines if line.strip()]  # Убираем пустые строки

        logger.debug(f"✅ Разделенные строки от пользователя {message.from_user.id}: {lines}")  # Логирование полученных строк

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

        # Логирование данных
        logger.debug(f"✅ Все данные прошли проверку. Отправляю информацию админу.")

        # Сохранение данных
        order_info = (
            f"📦 *Новый заказ:*\n"
            f"👤 *ФИО:* {full_name}\n"
            f"📞 *Телефон:* {phone}\n"
            f"🏠 *Адрес CDEK:* {address}\n"
            f"✉ *Email:* {email}"
        )

        # Отправляем администратору
        try:
            await bot.send_message(ADMIN_ID, order_info, parse_mode="Markdown")
            logger.debug(f"✅ Информация отправлена админу для пользователя {message.from_user.id}.")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке данных админу для пользователя {message.from_user.id}: {e}")
            await message.answer("❌ Произошла ошибка при отправке данных. Попробуйте позже.")
            return

        # Подтверждаем пользователю
        await message.answer("✅ Готово!\nВсе данные приняты, а я скоро свяжусь с тобой для оплаты 😊")
        await state.clear()  # Очистка состояния после завершения
    else:
        logger.error(f"❌ Ошибка: Получено сообщение от пользователя {message.from_user.id}, но состояние не соответствует ожидаемому.")
        await message.answer("❌ Произошла ошибка с состоянием. Пожалуйста, начни заново.")

# Функция для проверки данных
def validate_data(full_name, phone, address, email):
    # Приведение номера телефона к нужному формату
    phone = re.sub(r'\D', '', phone)  # Убираем все нецифровые символы

    if len(phone) == 11 and phone.startswith('8'):
        phone = '+7' + phone[1:]  # Преобразуем 8XXXXXXXXXX в +7XXXXXXXXXX
    elif len(phone) == 10:
        phone = '+7' + phone  # Преобразуем 9XXXXXXXXX в +7XXXXXXXXXX
    elif not re.match(r'^\+7\d{10}$', phone):
        return False, "❌ Некорректный номер телефона. Введите в формате +79991234567."

    # Проверка на корректность email
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
