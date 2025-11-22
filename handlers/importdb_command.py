import logging
import os
import sqlite3
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, filters

from config import ADMIN_ID
from database import DB_NAME

logger = logging.getLogger(__name__)

def auto_import_migration_data() -> bool:
    """
    Автоматически импортирует данные из migration_data.sql при старте бота (если файл существует).
    Полезно для восстановления БД после редеплоя на Railway.
    
    Returns:
        True если импорт был успешен, False если файл не найден или произошла ошибка.
    """
    sql_file_path = 'migration_data.sql'
    
    if not os.path.exists(sql_file_path):
        # Файл не существует — ничего не импортируем
        return False
    
    try:
        logger.info("🔄 Найден файл migration_data.sql — запуск автоматического импорта...")
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        if not sql_script.strip():
            logger.warning("⚠️  Файл migration_data.sql пуст, пропускаем импорт.")
            return False
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.executescript(sql_script)
            conn.commit()
        
        logger.info("✅ Автоматический импорт данных успешно завершен.")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при автоматическом импорте данных: {e}")
        return False

async def importdb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Временная команда для импорта данных из SQL-файла.
    Доступна только админу.
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        # Временный ответ для диагностики
        await update.message.reply_text(f"Доступ запрещен. Ваш ID: `{user_id}`, ожидаемый ADMIN_ID: `{ADMIN_ID}`.", parse_mode='Markdown')
        logger.warning(f"Попытка доступа к /importdb от пользователя с ID {user_id}. Ожидался {ADMIN_ID}.")
        return # Завершаем выполнение

    sql_file_path = 'migration_data.sql'

    if not os.path.exists(sql_file_path):
        await update.message.reply_text(f"Файл для импорта '{sql_file_path}' не найден.")
        return

    await update.message.reply_text("Начинаю импорт данных... Бот может не отвечать некоторое время.")
    logger.info("Начало выполнения SQL-скрипта для импорта данных.")

    try:
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.executescript(sql_script)
            conn.commit()

        logger.info("Импорт данных успешно завершен.")
        await update.message.reply_text("✅ Импорт данных успешно завершен!")

        # (Опционально) Удаляем файл после успешного импорта, чтобы не запустить его снова
        # os.remove(sql_file_path)
        # await update.message.reply_text("Файл миграции удален.")

    except Exception as e:
        logger.error(f"Ошибка при импорте данных из SQL-файла: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка при импорте: {e}")

importdb_handler = CommandHandler("importdb", importdb_command, filters=filters.ChatType.PRIVATE)
