"""
Модуль для загрузки и управления лором.
Содержит всё, что связано с персонажами, локациями, аномалиями, мутантами и текстами эпизодов.
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# --- Стеммер для более гибкого поиска ---
try:
    from nltk.stem.snowball import SnowballStemmer
    STEMMER = SnowballStemmer("russian")
except ImportError:
    logger.warning("Библиотека NLTK не найдена. Поиск будет работать без стемминга. Для установки: pip install nltk")
    STEMMER = None

# Попробуем подключить морфологический анализатор для нормализации (лемматизации)
try:
    import pymorphy2
    MORPH = pymorphy2.MorphAnalyzer()
    logger.info("pymorphy2 найден — включена лемматизация важный терминов.")
except Exception:
    MORPH = None
    logger.debug("pymorphy2 не найден — лемматизация отключена. Установите pymorphy2 для улучшения распознавания имён.")

# Список стоп-слов для исключения из поиска
STOP_WORDS = set([
    "а", "в", "и", "к", "на", "о", "об", "от", "по", "под", "при", "с", "со", "у", "же", "ли", "бы"
])


def get_stemmed_words(text: str) -> set:
    """Вспомогательная функция для получения набора основ слов из текста."""
    clean_text = ''.join(c for c in text.lower() if c.isalnum() or c.isspace())
    if not STEMMER:
        return {word for word in clean_text.split() if word not in STOP_WORDS}
    return {STEMMER.stem(word) for word in clean_text.split() if word not in STOP_WORDS}


def get_tokens(text: str) -> list:
    """Возвращает список токенов (слова) из текста в нижнем регистре, без стоп-слов."""
    clean_text = ''.join((c.lower() if (c.isalnum() or c.isspace()) else ' ') for c in text)
    return [w for w in clean_text.split() if w and w not in STOP_WORDS]


def get_lemmas(text: str) -> set:
    """Возвращает множество лемм (нормализованных форм) слов в тексте.
    Если pymorphy2 недоступен — возвращаем просто токены без стемминга.
    """
    tokens = get_tokens(text)
    if not MORPH:
        return set(tokens)
    lemmas = set()
    for t in tokens:
        try:
            lemmas.add(MORPH.parse(t)[0].normal_form)
        except Exception:
            lemmas.add(t)
    return lemmas


# --- РУЧНОЙ СПИСОК ЛОКАЦИЙ ---
KNOWN_LOCATIONS = {
    "кордон",
    "свалка",
    "агропром",
    "нии агропром",
    "подземелья агропрома",
    "бар",
    "бар 100 рентген",
    "темная долина",
    "тёмная долина", 
    "лаборатория x-18",
    "x-18",
    "x18",
    "дикая территория",
    "росток",
    "завод росток",
    "янтарь",
    "x-16",
    "x16",
    "лаборатория x-16",
    "армейские склады",
    "радар",
    "бункер управления выжигателем мозгов",
    "лаборатория x-10",
    "x-10",
    "x10",
    "припять",
    "саркофаг",
    "чаэс",
    "станция"
}

# --- РУЧНОЙ СПИСОК АНОМАЛИЙ ---
ANOMALIES = {
    "воронка",
    "карусель",
    "мясорубка",
    "жарка",
    "электра",
    "телепорт",
    "трамплин"
}

# --- РУЧНОЙ СПИСОК МУТАНТОВ ---
MUTANTS = {
    "кабан",
    "плоть",
    "слепой пёс",
    "слепая собака",
    "тушкан",
    "снорк",
    "кровосос",
    "излом",
    "контролёр",
    "полтергейст",
    "псевдогигант",
    "зомби",
    "зомбированный"
}

# --- РУЧНОЙ СПИСОК ГРУППИРОВОК ---
FACTIONS = {
    "одиночки",
    "одиночка",
    "бандиты",
    "долг",
    "свобода",
    "наёмники",
    "монолит",
    "военные",
    "учёные",
    "чистое небо",
    "ренегаты",
}

# --- РУЧНОЙ СПИСОК ВАЖНЫХ КЛЮЧЕВЫХ СЛОВ ---
IMPORTANT_KEYWORDS_RAW = {
    "зона",
    "большая земля",
    "сталкеры",
    "группировки",
    "артефакты",
    "аномалии",
    "мутанты",
    "центр зоны",
    "выброс",
}

# --- Предварительная обработка важных ключевых слов ---
STEMMED_IMPORTANT_KEYWORDS = set()

# Добавляем стемы для всех категорий
for keyword in IMPORTANT_KEYWORDS_RAW:
    STEMMED_IMPORTANT_KEYWORDS.update(get_stemmed_words(keyword))

for anomaly in ANOMALIES:
    STEMMED_IMPORTANT_KEYWORDS.update(get_stemmed_words(anomaly))

for mutant in MUTANTS:
    STEMMED_IMPORTANT_KEYWORDS.update(get_stemmed_words(mutant))

for faction in FACTIONS:
    STEMMED_IMPORTANT_KEYWORDS.update(get_stemmed_words(faction))

# --- Точное сопоставление важных терминов (без стемминга) ---
EXACT_IMPORTANT_KEYWORDS = set()

# Попробуем загрузить файл с персонажами и добавить имена в точный набор
try:
    characters_file_path = Path(__file__).resolve().parent.parent / "Lore" / "Персонажи и отношения.txt"
    if not characters_file_path.exists():
        characters_file_path = Path(__file__).resolve().parent.parent / "lore" / "Персонажи и отношения.txt"

    if characters_file_path.is_file():
        content = characters_file_path.read_text(encoding='utf-8')
        for line in content.splitlines():
            if ':' in line:
                names_part = line.split(':', 1)[0].strip()
                for raw_name in re.split(r"[,/;|()]", names_part):
                    character_name = raw_name.strip().lower()
                    if character_name and not character_name.startswith('#'):
                        IMPORTANT_KEYWORDS_RAW.add(character_name)
                        EXACT_IMPORTANT_KEYWORDS.add(character_name)
        logger.info(f"Загружено {len(EXACT_IMPORTANT_KEYWORDS)} имён персонажей (точный набор)")
except Exception as e:
    logger.debug(f"Не удалось загрузить персонажей для точного сопоставления: {e}")

# Обновляем стеммированные важные ключевые слова
for exact in list(EXACT_IMPORTANT_KEYWORDS):
    STEMMED_IMPORTANT_KEYWORDS.update(get_stemmed_words(exact))

# Нормализованные леммы для точных ключевых слов
EXACT_IMPORTANT_LEMMAS = set()
for exact in EXACT_IMPORTANT_KEYWORDS:
    if MORPH:
        try:
            EXACT_IMPORTANT_LEMMAS.add(MORPH.parse(exact)[0].normal_form)
        except Exception:
            EXACT_IMPORTANT_LEMMAS.add(exact)
    else:
        EXACT_IMPORTANT_LEMMAS.add(exact)

# --- Предварительная обработка локаций ---
STEMMED_LOCATIONS = {loc: get_stemmed_words(loc) for loc in KNOWN_LOCATIONS}

# --- Система управления лором ---
EPISODE_CHUNKS = []
GENERAL_CHUNKS = []

try:
    lore_dir = Path(__file__).resolve().parent.parent / "lore"
    episodes_dir = lore_dir / "episodes"
    
    # 1. Загружаем и разделяем на чанки файлы эпизодов
    if episodes_dir.is_dir():
        for file_path in episodes_dir.glob("*.txt"):
            relative_path_key = str(file_path.relative_to(lore_dir))
            try:
                content = file_path.read_text(encoding="utf-8")
                
                first_line, rest_of_content = content.split('\n', 1)
                file_locations = set()
                match = re.search(r'Локация\s*[:—-]?\s*(.+)', first_line, re.IGNORECASE)
                if match:
                    location_names_str = match.group(1).replace('.', '').strip()
                    found_locations = {name.strip().lower() for name in location_names_str.split(',') if name.strip()}
                    file_locations.update(found_locations)
                    logger.info(f"Для файла '{file_path.name}' определены локации: {list(file_locations)}")

                for chunk in content.split('\n\n'):
                    if chunk.strip():
                        chunk_text = chunk.strip()
                        EPISODE_CHUNKS.append({'source': relative_path_key, 'content': chunk_text, 'locations': file_locations, 'lemmas': get_lemmas(chunk_text)})
            except Exception as e:
                logger.error(f"Не удалось прочитать файл эпизода '{file_path}': {e}")

    # 2. Загружаем и разделяем на чанки общие файлы лора (в корне папки lore)
    for file_path in lore_dir.glob("*.txt"):
        relative_path_key = str(file_path.relative_to(lore_dir))
        try:
            content = file_path.read_text(encoding="utf-8")
            for chunk in content.split('\n\n'):
                if chunk.strip():
                    chunk_text = chunk.strip()
                    GENERAL_CHUNKS.append({'source': relative_path_key, 'content': chunk_text, 'locations': set(), 'lemmas': get_lemmas(chunk_text)})
        except Exception as e:
            logger.error(f"Не удалось прочитать общий файл лора '{file_path}': {e}")

    logger.info(f"Загружено {len(EPISODE_CHUNKS)} чанков из эпизодов и {len(GENERAL_CHUNKS)} общих чанков лора.")

except FileNotFoundError:
    logger.error("Папка 'lore' или её компоненты не найдены! Убедитесь, что существует структура 'lore/episodes/'")
except Exception as e:
    logger.exception(f"Ошибка при чтении файлов лора: {e}")
