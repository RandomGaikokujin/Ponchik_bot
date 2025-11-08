import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, filters

from config import ADMIN_ID
from database import get_last_n_records

logger = logging.getLogger(__name__)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправляет администратору статистику последних запросов из БД.
    """
    user_id = update.effective_user.id

    # --- ПРОВЕРКА ПРАВ АДМИНИСТРАТОРА ---
    if user_id != ADMIN_ID:
        logger.warning(f"Пользователь {update.effective_user.full_name} ({user_id}) попытался использовать команду /stats без прав.")
        return # Просто игнорируем команду, если ее вызвал не админ

    logger.info(f"Администратор ({user_id}) запросил статистику.")

    try:
        # Получаем последние 5 записей из базы данных
        records = get_last_n_records(5)

        if not records:
            await update.message.reply_text("В базе данных пока нет записей.")
            return

        response_text = "Последние 5 запросов:\n\n"
        for record in records:
            # Форматируем каждую запись для удобного чтения
            response_text += f"👤 **{record['username']}** ({record['timestamp']})\n"
            response_text += f"❓: *{record['user_message']}*\n"
            response_text += f"🤖: *{record['ai_response']}*\n"
            response_text += f"📊: {record['total_tokens']} токенов ({record['lore_chunks_sent']} чанков)\n\n"

        await update.message.reply_text(response_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при получении статистики из БД: {e}")
        await update.message.reply_text("Произошла ошибка при получении статистики.")

stats_handler = CommandHandler("stats", stats_command, filters=filters.ChatType.PRIVATE)