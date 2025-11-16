import logging
import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, filters

from config import ADMIN_ID
from database import DB_NAME  # Импортируем путь к файлу БД

logger = logging.getLogger(__name__)

async def getdb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /getdb: отправляет файл базы данных администратору.
    Доступна только админу.
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        logger.warning(f"Пользователь {user_id} попытался получить доступ к команде /getdb.")
        return

    try:
        if not os.path.exists(DB_NAME):
            await update.message.reply_text("Файл базы данных не найден.")
            logger.error(f"Администратор запросил БД, но файл не найден по пути: {DB_NAME}")
            return

        logger.info(f"Администратор {user_id} запросил файл базы данных. Отправка...")
        await update.message.reply_document(document=open(DB_NAME, 'rb'), filename=os.path.basename(DB_NAME))
    except Exception as e:
        logger.error(f"Ошибка при отправке файла базы данных: {e}")
        await update.message.reply_text("Произошла ошибка при отправке файла базы данных.")

getdb_handler = CommandHandler("getdb", getdb_command, filters=filters.ChatType.PRIVATE)