import logging
from typing import List
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
    def __init__(self, api_url : str = None, api_key : str = None):
        self.api_url = api_url or settings.DEEPSEEK_API_URL
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.prerequisite_map = {
            ('Django', 'Python'): True,
            ('FastAPI', 'Python'): True,
            ('Flask', 'Python'): True,
            ('NumPy', 'Python'): True,
            ('Scikit-learn', 'Python'): True,
            ('TensorFlow', 'Python'): True,
            ('PyTorch', 'Python'): True,
            ('DRF', 'Django'): True,
            ('Docker', 'Linux'): True,
            ('Kubernetes', 'Docker'): True,
            ('SQL', 'PostgreSQL'): True,
            ('SQL', 'MySQL'): True,
            ('Git', 'Linux'): False,
        }

    @breaker
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )

    def _call_api(self, prompt : str) -> str:
        headers = {
            "Authorization" : f"Bearer {self.api_key}",
            "Content-Type" : "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 10
        }
        response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
        logger.info(f"Status: {response.status_code}, Response: {response.text}")
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content'].strip().lower()


    def _build_prompt(self, skill_a : str, skill_b : str) -> str:
        return f'''Нужен ли для освоения навыка {skill_a} навык (prerequisite) {skill_b}? Ответь только "да" или "нет" без пояснений'''
    

    def _is_prerequisite(self, skill_a : Skill, skill_b : Skill) -> bool:
        name_a = skill_a.name
        name_b = skill_b.name

        if name_a == name_b:
            return False
        
        # проверка словаря
        pair = (name_a, name_b)
        if pair in self.prerequisite_map:
            logger.info(f"Prerequisite map hit for {name_a} and prereq {name_b}")
            return self.prerequisite_map[pair]
        
        # проверка кэша
        cache_key = f"prereq:{name_b}:skill:{name_a}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f"Cache hit for {name_a} and prereq {name_b}")
            return cached

        # вызов LLM
        try:
            prompt = self._build_prompt(name_a, name_b)
            answer = self._call_api(prompt)
            result = answer=='да'
            cache.set(cache_key, result, timeout=60*60*24*30)
            logger.info(f"LLM hit for {name_a} and prereq {name_b}, answer - {result}")
            return result
        except Exception as e:
            logger.error(f"Failed api call: {e}")
            return False

    # метод анализирует все пары из списка и добавляет пары в таблицу пререквизитов
    def extract_and_save_prerequisites(self, skills_list : List[Skill]):
        created_count = 0
        for skill_a, skill_b in combinations(skills_list, 2):
            if self._is_prerequisite(skill_a, skill_b):
                _, created = SkillPrerequisiteRepository.get_or_create(skill_a, skill_b)
                if created:
                    created_count += 1
                    logger.info(f"Added {skill_a}, prereq{skill_b} to db")
            if self._is_prerequisite(skill_b, skill_a):
                _, created = SkillPrerequisiteRepository.get_or_create(skill_b, skill_a)
                if created:
                    created_count += 1
                    logger.info(f"Added {skill_b}, prereq{skill_a} to db")
        return created_count
