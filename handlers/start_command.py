import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, filters
from database import create_or_update_user

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение. При необходимости добавляет кнопку подтверждения возраста."""
    user = update.effective_user
    logger.info(f"Пользователь {user.full_name} ({user.id}) запустил команду /start.")

    welcome_text = "Я - легенда Зоны Пончик! Ты принёс мне пожрать?"
    reply_markup = None

    # Проверяем, подтвержден ли возраст
    if not context.user_data.get("age_verified"):
        # Если возраст не подтвержден, добавляем пояснение в текст и короткую кнопку.
        welcome_text += "\n\nДля продолжения подтверди, что тебе есть 18 лет. Общение может содержать нецензурную лексику."
        keyboard = [
            [InlineKeyboardButton("Подтверждаю", callback_data="confirm_age")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    # Регистрируем пользователя в базе (или обновляем запись)
    try:
        user = update.effective_user
        tg_username = f"@{user.username}" if user.username else None
        create_or_update_user(user.full_name, tg_username, user.id)
    except Exception:
        logger.exception("Не удалось создать/обновить запись пользователя в БД при /start")

# Создаем фильтр, чтобы команда работала только в личных чатах.
# Это хорошая практика, чтобы бот не спамил в группах.
private_chat_filter = filters.ChatType.PRIVATE

# Создаем сам обработчик для команды /start, который будет работать только в личных чатах.
# Мы будем импортировать эту переменную в главном файле bot.py
start_handler = CommandHandler("start", start, filters=private_chat_filter)
