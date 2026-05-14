import logging
from typing import Dict, List, Tuple
from django.conf import settings
from django.core.cache import cache
import pybreaker
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from core.models import Skill
from core.repository import SkillPrerequisiteRepository
from itertools import combinations


logger = logging.getLogger(__name__)
breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

class PrerequisiteExtractor:
    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or settings.DEEPSEEK_API_URL
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.prerequisite_map = {
            ('Python', 'Django'): True,
            ('Python', 'FastAPI'): True,
            ('Python', 'Flask'): True,
            ('Python', 'NumPy'): True,
            ('Python', 'Scikit-learn'): True,
            ('Python', 'TensorFlow'): True,
            ('Python', 'PyTorch'): True,
            ('Django', 'DRF'): True,
            ('Linux', 'Docker'): True,
            ('Docker', 'Kubernetes'): True,
            ('PostgreSQL', 'SQL'): True,
            ('SQL', 'MySQL'): True,
            ('SQL', 'SQLAlchemy'): True,
            ('Python', 'Celery'): True,
            ('Тестирование', 'Тест-кейсы'): True,
            ('Тестирование', 'Тестовая документация'): True,
            # запрещаем ложные связи:
            ('Apache Spark', 'Python'): False,
            ('Git', 'Linux'): False,
        }

    @breaker
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )
    def _call_api(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 20  # для двух ответов
        }
        response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
        logger.info(f"Status: {response.status_code}, Response: {response.text}")
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content'].strip().lower()

    def _build_bidirectional_prompt(self, name_a: str, name_b: str) -> str:
        return f"""Ты эксперт в IT-образовании. Определи, является ли один навык необходимым prerequisite (базовым) для другого.
                    Навык A: "{name_a}"
                    Навык B: "{name_b}"
                    Ответь в формате "да, нет" / "нет, да" / "нет, нет" (без кавычек) на два вопроса:
                    1. Нужно ли сначала изучить "{name_a}", чтобы потом изучать "{name_b}"? (да/нет)
                    2. Нужно ли сначала изучить "{name_b}", чтобы потом изучать "{name_a}"? (да/нет)
                    Правила:
                    - Если A необходим для B, а B не нужен для A, то ответ "да, нет".
                    - Если B необходим для A, а A не нужен для B, то ответ "нет, да".
                    - Если они независимы, то "нет, нет".
                    - Никогда не отвечай "да, да".
                    Примеры:
                    - A="Python", B="Django" → ответ: да, нет
                    - A="Django", B="Python" → ответ: нет, да
                    - A="Git", B="Docker" → ответ: нет, нет
                    Твой ответ:"""

    def _parse_bidirectional_answer(self, answer: str, name_a: str, name_b: str) -> Tuple[bool, bool]:
        """Парсит строку вида 'да, нет' в два булевых значения."""
        answer_clean = answer.lower().strip()
        parts = [p.strip() for p in answer_clean.split(',')]
        if len(parts) != 2:
            # ищем отдельные слова "да"/"нет"
            a_to_b = 'да' in answer_clean
            b_to_a = False
            logger.warning(f"Unexpected answer format: '{answer}' for pair ({name_a}, {name_b})")
        else:
            a_to_b = parts[0] == 'да'
            b_to_a = parts[1] == 'да'
        
        if a_to_b and b_to_a:
            logger.warning(f"Both True for {name_a} <-> {name_b} – ignoring to prevent cycle")
            return False, False
        return a_to_b, b_to_a

    def _check_bidirectional(self, skill_a: Skill, skill_b: Skill) -> Tuple[bool, bool]:
        """
        Возвращает (a_to_b, b_to_a) – есть ли prerequisite от A к B и от B к A.
        Использует кэш и LLM.
        """
        name_a = skill_a.name
        name_b = skill_b.name
        if name_a == name_b:
            return False, False

        # Проверка словаря
        pair_key = (name_a, name_b)
        if pair_key in self.prerequisite_map:
            a_to_b = self.prerequisite_map[pair_key]
            b_to_a = self.prerequisite_map.get((name_b, name_a), False)
            return a_to_b, b_to_a

        # Проверка кэша (храним оба направления)
        cache_key = f"prereq_pair:{name_a}|{name_b}"
        cached = cache.get(cache_key)
        if cached is not None:
            a_to_b, b_to_a = cached
            logger.info(f"Cache hit for pair ({name_a}, {name_b}): {a_to_b}/{b_to_a}")
            return a_to_b, b_to_a

        # Запрос к LLM
        try:
            prompt = self._build_bidirectional_prompt(name_a, name_b)
            answer = self._call_api(prompt)
            a_to_b, b_to_a = self._parse_bidirectional_answer(answer, name_a, name_b)
            cache.set(cache_key, (a_to_b, b_to_a), timeout=60*60*24*30)
            logger.info(f"LLM result for ({name_a}, {name_b}): {a_to_b}/{b_to_a}")
            return a_to_b, b_to_a
        except Exception as e:
            logger.error(f"Failed to check prerequisites between {name_a} and {name_b}: {e}")
            return False, False

    def extract_and_save_prerequisites(self, skills_list: List[Skill], 
                                    importance_map: Dict[int, int] = None,
                                    min_freq: int = 2) -> int:
        skills_list = [s for s in skills_list if s is not None]
        created_count = 0

        for skill_a, skill_b in combinations(skills_list, 2):
            # Пропускаем soft-навыки
            if (hasattr(skill_a, 'skill_type') and skill_a.skill_type == Skill.SkillType.SOFT) or \
            (hasattr(skill_b, 'skill_type') and skill_b.skill_type == Skill.SkillType.SOFT):
                logger.debug(f"Skipping pair due to soft skill: {skill_a.name} - {skill_b.name}")
                continue

            # Фильтр по частоте
            if importance_map is not None:
                freq_a = importance_map.get(skill_a.id, 0)
                freq_b = importance_map.get(skill_b.id, 0)
                if freq_a < min_freq or freq_b < min_freq:
                    logger.debug(f"Пропуск пары {skill_a.name}-{skill_b.name}: частоты {freq_a}/{freq_b} ниже {min_freq}")
                    continue

            # Определяем направление зависимостей
            a_to_b, b_to_a = self._check_bidirectional(skill_a, skill_b)

            # Защита от циклов
            if a_to_b and b_to_a:
                logger.warning(f"Both directions for {skill_a.name} <-> {skill_b.name} – skipping pair")
                continue

            # Сохраняем A -> B
            if a_to_b:
                if not SkillPrerequisiteRepository.exists(skill_b, skill_a):
                    _, created = SkillPrerequisiteRepository.get_or_create(skill_b, skill_a)
                    if created:
                        created_count += 1
                        logger.info(f"Added {skill_a.name} -> {skill_b.name}")
                else:
                    logger.warning(f"Reverse link already exists, skipping {skill_a.name} -> {skill_b.name}")

            # Сохраняем B -> A
            if b_to_a:
                if not SkillPrerequisiteRepository.exists(skill_a, skill_b):
                    _, created = SkillPrerequisiteRepository.get_or_create(skill_a, skill_b)
                    if created:
                        created_count += 1
                        logger.info(f"Added {skill_b.name} -> {skill_a.name}")
                else:
                    logger.warning(f"Reverse link already exists, skipping {skill_b.name} -> {skill_a.name}")

        return created_count
    