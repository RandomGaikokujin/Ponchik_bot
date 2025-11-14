import logging
from telegram import Update
import re
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.constants import ChatAction
from typing import Dict, Any

# Импортируем утилиты и нужные компоненты из сервиса ИИ
from services.ai_service import get_ai_response, retrieve_relevant_lore
from handlers.utils import check_blacklist
from services.content_filter import filter_and_validate_response

logger = logging.getLogger(__name__)

def is_spam(text: str) -> bool:
    """
    Проверяет, является ли текст бессмысленным набором символов.
    Возвращает True, если сообщение похоже на спам.
    """
    length = len(text)
    if length < 150: # Короткие сообщения не проверяем, можно увеличить порог
        return False

    # Считаем количество букв и цифр
    alnum_count = sum(1 for char in text if char.isalnum())
    # Считаем количество уникальных символов
    unique_chars = len(set(text))

    # Если в длинном сообщении очень мало букв/цифр или очень мало уникальных символов, считаем это спамом.
    return (alnum_count / length < 0.4) or (unique_chars < 15 and length > 200)

def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для Telegram MarkdownV2."""
    # Список символов, которые нужно экранировать
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

from config import BOT_MAINTENANCE

@check_blacklist
async def echo_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отвечает на текстовое сообщение с помощью ИИ."""
    user = update.effective_user
    message_text = update.message.text
    logger.info(f"[РУ]{user.full_name} ({user.id}) написал: '{message_text}'")

    # Проверяем, не находится ли бот в режиме обновления
    if BOT_MAINTENANCE:
        response_text = "[РУ]Бот на обновлении. Напиши попозже!"
        logger.info(f"[РУ]Бот ответил {user.full_name} ({user.id}) (модель: system) (token usage: 0): '{response_text}'")
        await update.message.reply_text(response_text)
        return

    # Проверяем, подтвержден ли возраст, перед тем как отвечать
    if not context.user_data.get("age_verified"):
        logger.warning(f"Пользователь {user.full_name} ({user.id}) попытался написать боту без подтверждения возраста.")
        await update.message.reply_text("Сначала подтверди свой возраст, нажав /start.")
        return
        
    # Проверяем сообщение на спам
    if is_spam(message_text):
        logger.warning(f"Обнаружено спам-сообщение от {user.full_name} ({user.id}): '{message_text[:100]}...'")
        await update.message.reply_text("Кажется, это сообщение похоже на спам. Попробуй написать что-нибудь другое.")
        return

    # Проверяем на слишком короткое сообщение
    if len(message_text.strip()) <= 2:
        await update.message.reply_text("И чё это? Напиши подробнее, ёпрст")
        return
    
    # Проверяем сообщение на опасный контент (попытка провокации на токсичные темы)
    final_user_msg, was_msg_filtered = filter_and_validate_response(message_text)
    if was_msg_filtered:
        logger.warning(f"Сообщение от {user.full_name} ({user.id}) содержало запрещённый контент. Отказываем и предлагаем другую тему.")
        await update.message.reply_text("Это не мой базар. Поговорим о чём-нибудь другом.")
        return

    # --- Этапы 1 и 2: Поиск релевантного лора и формирование промпта ---
    # Получаем или создаем историю сообщений для этого пользователя
    chat_history = context.user_data.get("chat_history", [])
    # Добавляем текущее сообщение пользователя в историю для отправки в AI.
    # Команды уже отфильтрованы на уровне MessageHandler, так что здесь проверка не нужна.
    chat_history.append({"role": "user", "content": message_text})

    # Находим релевантные абзацы
    relevant_lore_chunk, lore_chunks_count = retrieve_relevant_lore(message_text)

    # --- Этап 3: Отправка запроса в ИИ ---
    # Обрезаем историю до последних 6 сообщений, чтобы не превышать лимит контекста
    # и сохраняем в user_data
    chat_history = chat_history[-6:]
    context.user_data["chat_history"] = chat_history

    try:
        # Показываем статус набора текста
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        # Получаем ответ от ИИ
        # Передаем полное имя пользователя для логирования
        response: Dict[str, Any] = await get_ai_response(chat_history, user.full_name or str(user.id))
        
        ai_message = response.get("message")
        used_model = response.get("model", "unknown")
        total_tokens = response.get("tokens", "N/A")

        # Если получили ответ, проверяем его на опасный контент
        if ai_message:
            # Фильтруем и проверяем ответ ИИ на токсичность
            final_response, was_filtered = filter_and_validate_response(ai_message)
            
            if was_filtered:
                logger.warning(f"Ответ ИИ был отфильтрован из-за токсичности для пользователя {user.full_name} ({user.id})")
            
            # Отправляем (возможно, отфильтрованный) ответ пользователю
            await update.message.reply_text(final_response)
            logger.info(f"[РУ]Бот ответил {user.full_name} ({user.id}) (модель: {used_model}) (token usage: {total_tokens}) (filtered: {was_filtered}): '{final_response}'")
            # Сохраняем ответ ассистента в историю только если это был успешный ответ от модели
            if used_model not in ['error', 'limit_exceeded']:
                chat_history.append({"role": "assistant", "content": final_response})
                # Сохраняем обновленную историю в user_data
                context.user_data["chat_history"] = chat_history
        else:
            logger.warning("ИИ вернул пустой ответ.")
            await update.message.reply_text("Спроси лучш чё-нибудь другое.")
    except Exception as e:
        logger.exception(f"Ошибка при запросе к ИИ: {e}")
        await update.message.reply_text("У меня какие-то проблемы с ИИ сейчас — попробуй позже.")

async def echo_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Функция-обертка для регистрации в MessageHandler, предотвращает двойные вызовы."""
    await echo_logic(update, context)

# Создаем фильтр для текстовых сообщений, которые не являются командами, в личных чатах.
echo_filter = filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE

# Создаем сам обработчик, который мы будем импортировать в главном файле.
echo_handler = MessageHandler(echo_filter, echo_handler_func)
