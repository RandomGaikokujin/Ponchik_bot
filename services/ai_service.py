"""
Публичный интерфейс AI сервиса.
Переэкспортирует основные функции и константы из подмодулей.
"""

# Публичные функции и константы
from .groq_client import get_ai_response, MODEL_TOKEN_LIMITS
from .lore_search import retrieve_relevant_lore

__all__ = [
    'get_ai_response',
    'retrieve_relevant_lore',
    'MODEL_TOKEN_LIMITS',
]
