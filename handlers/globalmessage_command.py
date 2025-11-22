import logging
import asyncio
import time
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, filters
from telegram.error import Forbidden, BadRequest, TelegramError

from config import ADMIN_ID
from database import get_all_users

logger = logging.getLogger(__name__)

async def globalmessage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправляет сообщение всем пользователям бота.
    Доступно только для ADMIN_ID.
    Использование: /globalmessage <текст сообщения>
    """
    user = update.effective_user
    if user.id != ADMIN_ID:
        logger.warning(f"Пользователь {user.full_name} ({user.id}) попытался использовать команду /globalmessage.")
        await update.message.reply_text("Эта команда доступна только админу.")
        return

    # Проверяем, есть ли текст сообщения
    if not context.args:
        await update.message.reply_text(
            "Пожалуйста, укажите текст сообщения после команды.\n"
            "Поддерживается HTML-разметка.\n\n"
            "<b>Пример:</b>\n"
            "<code>/globalmessage Привет!\n\nБот будет перезагружен через <b>5 минут</b>.</code>",
            parse_mode='HTML'
        )
        return

    # Получаем весь текст после команды /globalmessage
    # Это позволяет сохранять переносы строк и использовать форматирование
    command = "/globalmessage"
    message_to_send = update.message.text[len(command):].strip()

    users = get_all_users()

    if not users:
        await update.message.reply_text("В базе данных нет пользователей для рассылки.")
        return

    await update.message.reply_text(f"✅ Начинаю рассылку сообщения для {len(users)} пользователей. Это может занять некоторое время...")

    success_count = 0
    fail_count = 0
    start_time = time.time()

    for user_record in users:
        tg_id = user_record.get('tg_id')
        if not tg_id:
            continue

        # Собираем информацию о пользователе для логов
        user_info_parts = [f"ID: {tg_id}"]
        if user_record.get('tg_username'):
            user_info_parts.append(str(user_record.get('tg_username')))
        if user_record.get('nickname'):
            user_info_parts.append(str(user_record.get('nickname')))
        user_info_str = ", ".join(user_info_parts)

        try:
            await context.bot.send_message(chat_id=tg_id, text=message_to_send, parse_mode='HTML')
            success_count += 1
        except (Forbidden, BadRequest):
            # Forbidden: пользователь заблокировал бота.
            # BadRequest: неверный ID или пользователь удалил чат.
            fail_count += 1
            logger.warning(f"Не удалось отправить сообщение пользователю ({user_info_str}). Возможно, он заблокировал бота.")
        except TelegramError as e:
            fail_count += 1
            logger.error(f"Неизвестная ошибка при отправке сообщения пользователю ({user_info_str}): {e}")
        await asyncio.sleep(0.1) # Небольшая задержка, чтобы не превысить лимиты Telegram

    end_time = time.time()
    duration = round(end_time - start_time, 2)
    await update.message.reply_text(f"🏁 Рассылка завершена за {duration} сек.\n\n✅ Успешно отправлено: {success_count}\n❌ Не удалось отправить: {fail_count}")

globalmessage_handler = CommandHandler("globalmessage", globalmessage_command, filters=filters.ChatType.PRIVATE)