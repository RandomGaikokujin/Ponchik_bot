"""
Модуль для работы с Groq API и LLM моделями.
Содержит инициализацию клиента, список моделей, работу с запросами и обработку ответов.
"""
import logging
import re
from openai import AsyncOpenAI, RateLimitError

from config import GROQ_API_KEY, SYSTEM_PROMPT
from database import log_usage_to_db

logger = logging.getLogger(__name__)

# Инициализируем асинхронный клиент, настроенный на Groq
client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    max_retries=0,  # Отключаем автоматические повторные попытки при ошибке 429
    timeout=20.0,   # Устанавливаем общий таймаут на ответ в 20 секунд
)

# Список моделей для переключения в случае достижения лимитов.
MODELS_TO_TRY = [
    "groq/compound",
    "groq/compound-mini",
    "llama-3.3-70b-versatile",
    "moonshotai/kimi-k2-instruct",
    "moonshotai/kimi-k2-instruct-0905",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "qwen/qwen3-32b"
]

# --- СЛОВАРЬ С СУТОЧНЫМИ ЛИМИТАМИ ТОКЕНОВ ДЛЯ КАЖДОЙ МОДЕЛИ ---
MODEL_TOKEN_LIMITS = {
    "groq/compound": 123,
    "groq/compound-mini": 123,
    "llama-3.3-70b-versatile": 100_000,
    "moonshotai/kimi-k2-instruct": 300_000,
    "moonshotai/kimi-k2-instruct-0905": 300_000,
    "openai/gpt-oss-120b": 200_000,
    "openai/gpt-oss-20b": 200_000,
    "llama-3.1-8b-instant": 500_000,
    "meta-llama/llama-4-maverick-17b-128e-instruct": 500_000,
    "qwen/qwen3-32b": 500_000
}


def _strip_think_tags(text: str, model_name: str) -> str:
    """
    Обрабатывает теги <think> в ответе ИИ.
    - Для 'qwen/qwen3-32b': полностью удаляет блоки <think>...</think>.
    - Для других моделей: если найден тег <think>, возвращает сообщение об ошибке.
    """
    if "<think>" in text:
        if model_name == "qwen/qwen3-32b":
            # Для qwen просто удаляем блок
            processed_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
            return processed_text.strip()
        else:
            # Для остальных моделей возвращаем ошибку
            return "Ошибка. Ответ слишком большой."
    return text.strip()


async def get_ai_response(message_history: list, username: str) -> dict:
    """
    Отправляет историю сообщений в Groq. При достижении лимита одной модели,
    автоматически переключается на следующую из списка.
    
    Возвращает словарь с ключами:
    - 'message': строка ответа ИИ
    - 'model': название использованной модели
    - 'tokens': количество использованных токенов (если успешно)
    """
    from .lore_search import retrieve_relevant_lore
    
    # 1. Извлекаем релевантную информацию из лора на основе последнего сообщения пользователя
    user_query = message_history[-1]['content']
    relevant_lore_chunk, lore_chunks_count = retrieve_relevant_lore(user_query)

    # 2. Формируем динамический системный промпт
    dynamic_system_prompt = SYSTEM_PROMPT

    # Добавляем найденный чанк из эпизода, если он есть
    if relevant_lore_chunk:
        dynamic_system_prompt += f"\n\nВОСПОМИНАНИЕ ИЗ ТВОЕЙ ИСТОРИИ ДЛЯ КОНТЕКСТА:\n{relevant_lore_chunk}"

    messages_with_prompt = [{"role": "system", "content": dynamic_system_prompt}] + message_history

    for model in MODELS_TO_TRY:
        try:
            logger.info(f"Отправка запроса в Groq (модель: {model}) с последним сообщением: '{user_query}'")
            
            # Устанавливаем лимит токенов для всех моделей, кроме qwen/qwen3-32b
            max_tokens_for_model = None if model == "qwen/qwen3-32b" else 150

            response = await client.chat.completions.create(
                model=model,
                messages=messages_with_prompt,
                temperature=0.5,
                max_tokens=max_tokens_for_model,
            )
            raw_message = response.choices[0].message.content
            ai_message = _strip_think_tags(raw_message, model)
            # Temporary log: raw AI message before processing
            logger.info(f"Raw AI Message: {raw_message}")

            # Логируем использование токенов в консоль и в БД
            logger.info(f"Token Usage: {username} - {response.usage.total_tokens} (Total)")
            log_usage_to_db(username, user_query, response.usage, ai_message, lore_chunks_count, model)
            return {
                "message": ai_message,
                "model": model,
                "tokens": response.usage.total_tokens
            }
        except RateLimitError:
            logger.warning(f"Достигнут лимит для модели ({model}). Переключаюсь на следующую.")
            continue  # Переходим к следующей модели в цикле
        except Exception as e:
            # Специальная обработка ошибки "Request Entity Too Large"
            if "Error code: 413" in str(e) and "Request Entity Too Large" in str(e):
                logger.warning(f"Ошибка 413 (Request Too Large) с моделью {model}. Попытка отправить запрос без лора.")
                return await get_ai_response_without_lore(message_history, model, username)

            logger.error(f"Критическая ошибка при обращении к Groq API с моделью {model}: {e}")
            return {"message": "Хм, чёт у меня какие-то неполадки... Напиши потом.", "model": "error"}

    # Этот код выполнится, только если все модели из списка исчерпали лимиты
    logger.error("Все доступные модели исчерпали свои лимиты.")
    return {
        "message": "Мля, я заманался с тобой болтать. Приходи в другой раз. (токены закончились, напиши через несколько часов)",
        "model": "limit_exceeded"
    }
    

async def get_ai_response_without_lore(message_history: list, model: str, username: str) -> dict:
    """Запасной метод для отправки запроса без RAG-контекста."""
    try:
        logger.info(f"Повторная отправка запроса в Groq (модель: {model}) без лора.")
        base_prompt = SYSTEM_PROMPT
        messages_with_prompt = [{"role": "system", "content": base_prompt}] + message_history

        # Устанавливаем лимит токенов для всех моделей, кроме qwen/qwen3-32b
        max_tokens_for_model = None if model == "qwen/qwen3-32b" else 150

        response = await client.chat.completions.create(
            model=model,
            messages=messages_with_prompt,
            temperature=0.5,
            max_tokens=max_tokens_for_model,
        )
        raw_message = response.choices[0].message.content
        ai_message = _strip_think_tags(raw_message, model)
        logger.info(f"Token Usage (without lore): {username} - {response.usage.total_tokens} (Total)")
        log_usage_to_db(username, message_history[-1]['content'], response.usage, ai_message, lore_chunks_count=0, model_name=model)
        return {
            "message": ai_message,
            "model": model,
            "tokens": response.usage.total_tokens
        }
    except Exception as e:
        logger.error(f"Критическая ошибка при обращении к Groq API с моделью {model}: {e}")
        return {"message": "Хм, чёт у меня какие-то неполадки... Напиши потом.", "model": "error"}
