import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from config import BOT_MAINTENANCE, ADMIN_ID

logger = logging.getLogger(__name__)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отвечает на медиафайлы сообщением о том, что бот их не распознает."""
    user = update.effective_user
    logger.info(f"Пользователь {user.full_name} ({user.id}) отправил медиафайл, который не поддерживается.")

    # Если бот на обслуживании и это не админ, отвечаем и выходим
    if BOT_MAINTENANCE and user.id != ADMIN_ID:
        response_text = "Бот на обновлении. Напиши попозже!"
        logger.info(f"Отвечаем на медиафайл сообщением о тех. работах для {user.full_name} ({user.id}).")
        await update.message.reply_text(response_text)
        return

    # Проверяем, подтвержден ли возраст, так как это общая проверка для всех взаимодействий
    if not context.user_data.get("age_verified"):
        logger.warning(f"Пользователь {user.full_name} ({user.id}) попытался отправить медиа без подтверждения возраста.")
        await update.message.reply_text("Сначала подтверди свой возраст, нажав /start.")
        return

    # Ответ в стиле Пончика
    response_text = "Сорян, но я пока не распознаю стикеры, картинки, видео или аудио"
    await update.message.reply_text(response_text)

# Создаем фильтр для различных типов медиа в личных чатах.
media_filter = (
    filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE |
    filters.Sticker.ALL | filters.VIDEO_NOTE | filters.Document.ALL
) & filters.ChatType.PRIVATE

# Создаем сам обработчик, который мы будем импортировать в главном файле.
media_handler = MessageHandler(media_filter, handle_media)