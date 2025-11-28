import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, filters

from config import ADMIN_ID

logger = logging.getLogger(__name__)

async def helpadm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /helpadm: показывает список доступных команд для администратора.
    Доступна только админу.
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        logger.warning(f"Пользователь {user_id} попытался получить доступ к команде /helpadm.")
        # Не отвечаем ничего, чтобы не привлекать внимание к команде
        return

    admin_commands_text = (
        "<b>Команды администратора:</b>\n\n"
        "<code>/stats</code> — Показать статистику использования моделей за сегодня/вчера/позавчера.\n\n"
        "<code>/topusers</code> — Показать топ-20 пользователей по активности за выбранный день.\n\n"
        "<code>/cdcheck</code> — Проверить кулдауны в группах.\n\n"
        "<code>/getdb</code> — Получить файл базы данных.\n\n"
        "<code>/globalmessage &lt;текст&gt;</code> — Написать сообщение всем от бота."
    )

    await update.message.reply_text(text=admin_commands_text, parse_mode=ParseMode.HTML)


helpadm_handler = CommandHandler("helpadm", helpadm_command, filters=filters.ChatType.PRIVATE)