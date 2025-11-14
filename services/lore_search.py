"""
Продвинутый модуль поиска лора с многоуровневой релевантностью и контекстным анализом.
Заменяет lore_retrieval.py с более интеллектуальным подходом.
"""
import logging
import re
from typing import List, Dict, Tuple, Optional

from .lore_structure import get_lore_structure, Character, Location, Anomaly, Mutant
from .lore_loader import (
    get_stemmed_words, get_lemmas, get_tokens, STEMMER, STOP_WORDS
)

logger = logging.getLogger(__name__)


def _fuzzy_match(word: str, target: str, min_overlap: float = 0.7) -> bool:
    """
    Нечеткое сравнение слов (для обработки падежей и вариантов).
    Проверяет совпадение первых N символов (корня слова).
    
    Args:
        word: Слово из запроса
        target: Слово из индекса
        min_overlap: Минимальная доля совпадения (0.7 = 70%)
    
    Returns:
        True если слова достаточно похожи
    """
    if word == target:
        return True
    
    # Если одно слово является началом другого (обработка падежей)
    if len(word) > 3 and len(target) > 3:
        min_len = min(len(word), len(target))
        common = sum(1 for i in range(min_len) if word[i] == target[i])
        overlap = common / max(len(word), len(target))
        if overlap >= min_overlap:
            return True
    
    return False


class LoreContextEngine:
    """
    Интеллектуальный движок поиска контекста лора.
    
    Стратегия:
    1. Определяет тип запроса (персонаж, локация, аномалия, мутант или общее описание)
    2. Для каждого типа собирает максимально полезный контекст
    3. Учитывает связанные сущности (персонажи в локации, враги персонажа и т.д.)
    4. Возвращает оптимальный набор информации для контекста ИИ
    """
    
    def __init__(self):
        self.lore = get_lore_structure()
        self.query_history: List[str] = []
    
    def retrieve_context(self, query: str, max_tokens: int = 4000) -> Tuple[str, Dict]:
        """
        Главный метод для получения контекста по запросу.
        
        Args:
            query: Запрос пользователя
            max_tokens: Максимальное количество токенов в ответе
            
        Returns:
            Кортеж (контекст_для_ИИ, метаданные_поиска)
        """
        logger.info(f"Получен запрос: '{query}'")
        
        metadata = {
            'query': query,
            'entity_type': 'unknown',
            'found_entities': [],
            'context_sources': [],
            'relevance_score': 0.0,
            'token_count': 0
        }
        
        # Парсим запрос для выявления типа сущности
        entity_type, matched_entities = self._parse_query(query)
        metadata['entity_type'] = entity_type
        metadata['found_entities'] = matched_entities
        
        if not matched_entities:
            logger.info("Не найдены конкретные сущности, используем общий поиск")
            context, score = self._retrieve_general_context(query)
        else:
            # Выбираем стратегию в зависимости от типа сущности
            if entity_type == 'character':
                context, score = self._retrieve_character_context(matched_entities, query)
            elif entity_type == 'location':
                context, score = self._retrieve_location_context(matched_entities, query)
            elif entity_type == 'anomaly':
                context, score = self._retrieve_anomaly_context(matched_entities, query)
            elif entity_type == 'mutant':
                context, score = self._retrieve_mutant_context(matched_entities, query)
            elif entity_type == 'term':
                context, score = self._retrieve_term_context(matched_entities, query)
            elif entity_type == 'faction':
                context, score = self._retrieve_faction_context(matched_entities, query)
            else:
                context, score = self._retrieve_general_context(query)
        
        metadata['relevance_score'] = score
        metadata['token_count'] = len(context.split())
        
        logger.info(f"Контекст составлен. Тип: {entity_type}, Релевантность: {score:.2f}")
        
        return context, metadata
    
    def _parse_query(self, query: str) -> Tuple[str, List[str]]:
        """
        Определяет тип запроса и извлекает упомянутые сущности.
        Проверяет: персонажи, локации, аномалии, мутанты, и выполняет общий поиск.
        
        Returns:
            (тип_сущности, список_имён_или_ключевых_слов)
        """
        query_lower = query.lower()
        query_tokens = get_tokens(query)
        
        logger.debug(f"Query tokens: {query_tokens}")
        logger.debug(f"Query lower: {query_lower}")
        
        # Проверяем на предмет персонажей
        found_characters = []
        
        # Сначала проверяем через токены (точное совпадение)
        for token in query_tokens:
            if token in self.lore.char_aliases_index:
                canonical_key = self.lore.char_aliases_index[token]
                char = self.lore.characters.get(canonical_key)
                if char:
                    found_characters.append(char.name)
        
        # Если через токены не нашли, проверяем через индекс напрямую (точное совпадение в query_lower)
        if not found_characters:
            for alias_key in self.lore.char_aliases_index.keys():
                if alias_key in query_lower:
                    canonical_key = self.lore.char_aliases_index[alias_key]
                    char = self.lore.characters.get(canonical_key)
                    if char and char.name not in found_characters:
                        found_characters.append(char.name)
        
        # Если все еще не нашли, используем нечеткий поиск (обработка падежей)
        if not found_characters:
            for alias_key in self.lore.char_aliases_index.keys():
                for query_word in query_tokens:
                    if _fuzzy_match(query_word, alias_key):
                        canonical_key = self.lore.char_aliases_index[alias_key]
                        char = self.lore.characters.get(canonical_key)
                        if char and char.name not in found_characters:
                            found_characters.append(char.name)
                            break
        
        if found_characters:
            logger.debug(f"Найдены персонажи: {found_characters}")
            return 'character', found_characters
        
        # Проверяем на предмет локаций
        found_locations = []
        
        # Сначала через токены (точное совпадение)
        for token in query_tokens:
            if token in self.lore.loc_aliases_index:
                canonical_key = self.lore.loc_aliases_index[token]
                loc = self.lore.locations.get(canonical_key)
                if loc:
                    found_locations.append(loc.name)
        
        # Если не нашли, проверяем через индекс напрямую (точное совпадение в query_lower)
        if not found_locations:
            for alias_key in self.lore.loc_aliases_index.keys():
                if alias_key in query_lower:
                    canonical_key = self.lore.loc_aliases_index[alias_key]
                    loc = self.lore.locations.get(canonical_key)
                    if loc and loc.name not in found_locations:
                        found_locations.append(loc.name)
        
        # Если все еще не нашли, используем нечеткий поиск (обработка падежей)
        if not found_locations:
            for alias_key in self.lore.loc_aliases_index.keys():
                for query_word in query_tokens:
                    if _fuzzy_match(query_word, alias_key):
                        canonical_key = self.lore.loc_aliases_index[alias_key]
                        loc = self.lore.locations.get(canonical_key)
                        if loc and loc.name not in found_locations:
                            found_locations.append(loc.name)
                            break
        
        if found_locations:
            logger.debug(f"Найдены локации: {found_locations}")
            return 'location', found_locations
        
        # Проверяем на предмет аномалий
        found_anomalies = []
        for token in query_tokens:
            anom = self.lore.anomalies.get(token.lower())
            if anom:
                found_anomalies.append(anom.name)
        
        # Также проверяем прямой поиск в лоре
        if not found_anomalies:
            for anom_key, anom in self.lore.anomalies.items():
                if anom_key in query_lower:
                    if anom.name not in found_anomalies:
                        found_anomalies.append(anom.name)
        
        # Нечеткий поиск для аномалий
        if not found_anomalies:
            for anom_key, anom in self.lore.anomalies.items():
                for query_word in query_tokens:
                    if _fuzzy_match(query_word, anom_key):
                        if anom.name not in found_anomalies:
                            found_anomalies.append(anom.name)
                            break
        
        if found_anomalies:
            logger.debug(f"Найдены аномалии: {found_anomalies}")
            return 'anomaly', found_anomalies
        
        # Проверяем на предмет мутантов
        found_mutants = []
        for token in query_tokens:
            mut = self.lore.mutants.get(token.lower())
            if mut:
                found_mutants.append(mut.name)
        
        # Также проверяем прямой поиск
        if not found_mutants:
            for mutant_key, mut in self.lore.mutants.items():
                if mutant_key in query_lower:
                    if mut.name not in found_mutants:
                        found_mutants.append(mut.name)
        
        # Нечеткий поиск для мутантов
        if not found_mutants:
            for mutant_key, mut in self.lore.mutants.items():
                for query_word in query_tokens:
                    if _fuzzy_match(query_word, mutant_key):
                        if mut.name not in found_mutants:
                            found_mutants.append(mut.name)
                            break
        
        if found_mutants:
            logger.debug(f"Найдены мутанты: {found_mutants}")
            return 'mutant', found_mutants
        
        # Проверяем на предмет терминов
        found_terms = []
        for term_key, term in self.lore.terms.items():
            if term_key in query_lower:
                if term.name not in found_terms:
                    found_terms.append(term.name)
        
        # Нечеткий поиск для терминов
        if not found_terms:
            for term_key, term in self.lore.terms.items():
                for query_word in query_tokens:
                    if _fuzzy_match(query_word, term_key):
                        if term.name not in found_terms:
                            found_terms.append(term.name)
                            break
        
        if found_terms:
            logger.debug(f"Найдены термины: {found_terms}")
            return 'term', found_terms
        
        # Проверяем на предмет группировок
        found_factions = []
        for faction_key, faction in self.lore.factions.items():
            if faction_key in query_lower:
                if faction.name not in found_factions:
                    found_factions.append(faction.name)
        
        # Нечеткий поиск для группировок
        if not found_factions:
            for faction_key, faction in self.lore.factions.items():
                for query_word in query_tokens:
                    if _fuzzy_match(query_word, faction_key):
                        if faction.name not in found_factions:
                            found_factions.append(faction.name)
                            break
        
        if found_factions:
            logger.debug(f"Найдены группировки: {found_factions}")
            return 'faction', found_factions
        
        # Общий поиск
        return 'general', []
    
    def _retrieve_character_context(self, character_names: List[str], query: str) -> Tuple[str, float]:
        """
        Собирает контекст для персонажа.
        Включает: основная информация + отношения + упоминания в эпизодах
        """
        context_parts = []
        relevance = 0.0
        
        for char_name in character_names:
            character = self.lore.find_character(char_name)
            if not character:
                continue
            
            relevance += 50.0
            
            # 1. Основная информация о персонаже
            context_parts.append(character.get_full_info())
            
            # 2. Ищем упоминания других персонажей, если о них спрашивают
            related_context = self._find_related_context(character, query)
            if related_context:
                context_parts.append("\n\n" + related_context)
                relevance += 10.0
            
            # 3. Добавляем информацию о локации персонажа, если она есть
            if hasattr(character, 'location') and character.location:
                location = self.lore.find_location(character.location)
                if location:
                    context_parts.append(f"\n\n**О локации {location.name}:**\n{location.description}")
                    relevance += 5.0
        
        context = "\n".join(context_parts)
        return context, min(relevance, 100.0)
    
    def _retrieve_location_context(self, location_names: List[str], query: str) -> Tuple[str, float]:
        """
        Собирает контекст для локации.
        Включает: описание + связанные локации + персонажи в локации
        """
        context_parts = []
        relevance = 0.0
        
        for loc_name in location_names:
            location = self.lore.find_location(loc_name)
            if not location:
                continue
            
            relevance += 40.0
            
            # Основная информация о локации
            parts = [f"**{location.name}**"]
            if location.aliases:
                parts.append(f"Также известна как: {', '.join(sorted(location.aliases))}")
            parts.append(f"\n{location.description}")
            
            context_parts.append("\n".join(parts))
            
            # Связанные локации
            if location.related_locations:
                context_parts.append(f"\nСвязанные локации: {', '.join(sorted(location.related_locations))}")
                relevance += 3.0
            
            # Ищем персонажей, связанных с этой локацией
            related_chars = self._find_characters_in_location(location)
            if related_chars:
                context_parts.append(f"\nПерсонажи в локации:\n" + "\n".join(related_chars))
                relevance += 5.0
        
        context = "\n".join(context_parts)
        return context, min(relevance, 100.0)
    
    def _retrieve_anomaly_context(self, anomaly_names: List[str], query: str) -> Tuple[str, float]:
        """Собирает контекст для аномалии"""
        context_parts = []
        relevance = 0.0
        
        for anom_name in anomaly_names:
            anomaly = self.lore.find_anomaly(anom_name)
            if not anomaly:
                continue
            
            relevance += 35.0
            
            parts = [f"**{anomaly.name}**"]
            if anomaly.aliases:
                parts.append(f"Другие названия: {', '.join(sorted(anomaly.aliases))}")
            parts.append(f"\n{anomaly.description}")
            
            context_parts.append("\n".join(parts))
        
        context = "\n".join(context_parts)
        return context, min(relevance, 100.0)
    
    def _retrieve_mutant_context(self, mutant_names: List[str], query: str) -> Tuple[str, float]:
        """Собирает контекст для мутанта"""
        context_parts = []
        relevance = 0.0
        
        for mutant_name in mutant_names:
            mutant = self.lore.find_mutant(mutant_name)
            if not mutant:
                continue
            
            relevance += 35.0
            
            parts = [f"**{mutant.name}**"]
            if mutant.aliases:
                parts.append(f"Другие названия: {', '.join(sorted(mutant.aliases))}")
            parts.append(f"\n{mutant.description}")
            
            context_parts.append("\n".join(parts))
        
        context = "\n".join(context_parts)
        return context, min(relevance, 100.0)
    
    def _retrieve_general_context(self, query: str) -> Tuple[str, float]:
        """
        Общий поиск по ключевым словам, когда тип сущности неизвестен.
        Поиск в: персонажи, локации, аномалии, мутанты, и другие данные лора.
        """
        query_lower = query.lower()
        query_tokens = get_tokens(query)
        
        results = []
        context_parts = []
        relevance_scores = []
        
        # 1. Поиск в описаниях персонажей
        for char_key, character in self.lore.characters.items():
            if self._contains_query_words(character.description, query_tokens):
                relevance = self._calculate_relevance(character.description, query_tokens)
                context_parts.append(f"**Персонаж: {character.name}**\n{character.description}")
                relevance_scores.append(relevance)
        
        # 2. Поиск в локациях
        for loc_key, location in self.lore.locations.items():
            if self._contains_query_words(location.description, query_tokens):
                relevance = self._calculate_relevance(location.description, query_tokens)
                context_parts.append(f"**Локация: {location.name}**\n{location.description}")
                relevance_scores.append(relevance)
        
        # 3. Поиск в аномалиях
        for anom_key, anomaly in self.lore.anomalies.items():
            if self._contains_query_words(anomaly.description, query_tokens):
                relevance = self._calculate_relevance(anomaly.description, query_tokens)
                context_parts.append(f"**Аномалия: {anomaly.name}**\n{anomaly.description}")
                relevance_scores.append(relevance)
        
        # 4. Поиск в мутантах
        for mut_key, mutant in self.lore.mutants.items():
            if self._contains_query_words(mutant.description, query_tokens):
                relevance = self._calculate_relevance(mutant.description, query_tokens)
                context_parts.append(f"**Мутант: {mutant.name}**\n{mutant.description}")
                relevance_scores.append(relevance)
        
        if not context_parts:
            logger.warning(f"Не найден контекст для запроса: {query}")
            return "", 0.0
        
        # Сортируем по релевантности
        sorted_parts = [x for _, x in sorted(zip(relevance_scores, context_parts), reverse=True)]
        context = "\n\n---\n\n".join(sorted_parts[:5])  # Берём топ 5
        
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
        return context, min(avg_relevance, 100.0)

    def _retrieve_term_context(self, term_names: List[str], query: str) -> Tuple[str, float]:
        """Возвращает контекст для термина/определения"""
        context_parts = []
        relevance = 0.0

        for term_name in term_names:
            term = self.lore.terms.get(term_name.lower())
            if not term:
                continue
            relevance += 30.0
            parts = [f"**Термин: {term.name}**"]
            if term.aliases:
                parts.append(f"Алиасы: {', '.join(sorted(term.aliases))}")
            parts.append(f"\n{term.definition}")
            if term.context:
                parts.append(f"\nКонтекст: {term.context}")
            context_parts.append('\n'.join(parts))

        return '\n\n---\n\n'.join(context_parts), min(relevance, 100.0)

    def _retrieve_faction_context(self, faction_names: List[str], query: str) -> Tuple[str, float]:
        """Возвращает контекст для группировки/фракции"""
        context_parts = []
        relevance = 0.0

        for fac_name in faction_names:
            faction = self.lore.factions.get(fac_name.lower())
            if not faction:
                continue
            relevance += 35.0
            parts = [f"**Группировка: {faction.name}**"]
            if faction.aliases:
                parts.append(f"Алиасы: {', '.join(sorted(faction.aliases))}")
            parts.append(f"\n{faction.description}")
            if faction.goals:
                parts.append(f"\nЦели: {faction.goals}")
            if faction.members:
                parts.append(f"\nЧлены: {', '.join(sorted(faction.members))}")
            context_parts.append('\n'.join(parts))

        return '\n\n---\n\n'.join(context_parts), min(relevance, 100.0)
    
    def _contains_query_words(self, text: str, query_tokens: List[str]) -> bool:
        """Проверяет, содержит ли текст слова из запроса"""
        text_lower = text.lower()
        text_tokens = get_tokens(text)
        
        for query_word in query_tokens:
            if query_word in text_tokens:
                return True
            if query_word in text_lower:
                return True
        
        return False
    
    def _calculate_relevance(self, text: str, query_tokens: List[str]) -> float:
        """Рассчитывает релевантность текста по количеству совпадений ключевых слов"""
        text_lower = text.lower()
        text_tokens = get_tokens(text)
        
        matches = 0
        for query_word in query_tokens:
            if query_word in text_tokens:
                matches += 2
            elif query_word in text_lower:
                matches += 1
        
        # Нормализуем: релевантность от 0 до 100
        return min((matches / max(len(query_tokens), 1)) * 20, 100.0)
    
    def _find_related_context(self, character: Character, query: str) -> str:
        """
        Ищет связанную информацию о персонаже.
        Например, если просят про врагов персонажа или его друзей.
        """
        related_parts = []
        query_lower = query.lower()
        
        # Ищем связанных персонажей в описании
        if hasattr(character, 'related_characters') and character.related_characters:
            # Проверяем, не просят ли про друзей/врагов/связи
            if any(word in query_lower for word in ['друг', 'враг', 'группа', 'брат', 'связь', 'знаком']):
                related_parts.append(f"\nСвязанные персонажи: {', '.join(character.related_characters)}")
        
        # Ищем упоминания этого персонажа в описаниях других персонажей
        mentions = []
        char_name_lower = character.name.lower()
        for other_key, other_char in self.lore.characters.items():
            if other_key != char_name_lower:
                if char_name_lower in other_char.description.lower():
                    mentions.append(f"Упомянут(а) в информации о {other_char.name}")
        
        if mentions and len(mentions) <= 3:  # Не добавляем слишком много
            related_parts.extend(mentions[:2])
        
        return "\n".join(related_parts)
    
    def _find_characters_in_location(self, location: Location) -> List[str]:
        """Ищет персонажей, связанных с локацией"""
        found_chars = []
        loc_name_lower = location.name.lower()
        
        for char_key, character in self.lore.characters.items():
            # Проверяем упоминание локации в описании персонажа
            if loc_name_lower in character.description.lower():
                found_chars.append(f"- {character.name}: {character.description[:100]}...")
        
        return found_chars[:5]  # Максимум 5 персонажей


# Глобальный экземпляр движка
_ENGINE = None


def get_lore_engine() -> LoreContextEngine:
    """Возвращает глобальный экземпляр движка поиска лора"""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = LoreContextEngine()
    return _ENGINE


def retrieve_relevant_lore(user_query: str) -> Tuple[str, int]:
    """
    Совместимая функция с текущим интерфейсом.
    Возвращает кортеж (контекст, количество найденных сущностей).
    """
    engine = get_lore_engine()
    context, metadata = engine.retrieve_context(user_query)
    
    entity_count = len(metadata.get('found_entities', []))
    
    # Логируем выбранный контекст
    if context:
        logger.info(f"\n{'='*80}\nВЫБРАННЫЙ КОНТЕКСТ ИЗ ЛОРА:\n{'='*80}\n{context}\n{'='*80}\n")
    
    return context, entity_count
