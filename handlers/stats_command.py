import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, filters
from datetime import date, timedelta

# Импортируем функцию для получения статистики из БД
from database import get_stats_for_date
# Импортируем ID админа для проверки прав
from services.ai_service import MODEL_TOKEN_LIMITS
# Импортируем ID админа для проверки прав
from config import ADMIN_ID

logger = logging.getLogger(__name__)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправляет меню для выбора даты для просмотра статистики.
    Доступно только администратору.
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        logger.warning(f"Пользователь {user_id} попытался получить доступ к команде /stats.")
        await update.message.reply_text("Эта команда доступна только админу.")
        return

    today = date.today()
    keyboard = [
        [
            InlineKeyboardButton("Сегодня", callback_data=f"stats_{today.strftime('%Y-%m-%d')}"),
            InlineKeyboardButton("Вчера", callback_data=f"stats_{(today - timedelta(days=1)).strftime('%Y-%m-%d')}")
        ],
        [
            InlineKeyboardButton("Позавчера", callback_data=f"stats_{(today - timedelta(days=2)).strftime('%Y-%m-%d')}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите дату для просмотра статистики:", reply_markup=reply_markup)

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает нажатие на кнопку с датой и выводит статистику.
    """
    query = update.callback_query
    await query.answer()

    # Извлекаем дату из callback_data (например, 'stats_2025-11-09')
    date_str = query.data.split('_')[1]
    
    logger.info(f"Администратор запросил статистику за {date_str}.")

    stats = get_stats_for_date(date_str)

    if not stats:
        await query.edit_message_text(f"За {date_str} нет данных об использовании моделей.")
        return

    # Форматируем красивый отчет
    total_requests = sum(s['requests'] for s in stats)
    total_tokens = sum(s['total_tokens'] for s in stats)
    
    # Формируем заголовок с общей статистикой (с двойным переносом строки после каждой строки)
    header_lines = [
        f"📊 *Статистика за {date_str}*",
        f"*Всего запросов:* {total_requests}",
        f"*Всего токенов:* {total_tokens:,}".replace(',', ' '),
        "---"
    ]
    
    # Формируем список моделей (без дополнительных пустых строк между ними)
    model_lines = []
    for stat in stats:
        model_name = stat['model_name']
        spent_tokens = stat['total_tokens']
        # Получаем лимит для модели, если он не найден - ставим 0
        max_tokens = MODEL_TOKEN_LIMITS.get(model_name, 0)
        max_tokens_str = f"(макс: {max_tokens:,})".replace(',', ' ') if max_tokens > 0 else ""
        model_lines.append(f"• `{model_name}`: *{stat['requests']}* запр., *{spent_tokens:,}* токенов {max_tokens_str}".replace(',', ' '))

    # Собираем финальное сообщение:
    # - Заголовок с двойными переносами между строками
    # - Пустая строка перед списком моделей
    # - Список моделей с двойными переносами между ними
    message = "\n\n".join(header_lines) + "\n\n" + "\n\n".join(model_lines)
    
    await query.edit_message_text(message, parse_mode='Markdown')

stats_handler = CommandHandler("stats", stats_command, filters=filters.ChatType.PRIVATE)
stats_callback_handler = CallbackQueryHandler(stats_callback, pattern="^stats_")