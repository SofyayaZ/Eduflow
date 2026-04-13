from django.core.cache import cache
from django.conf import settings
import logging
import re
import pybreaker
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from core.models import Skill
from core.repository import SkillRepository


logger = logging.getLogger(__name__)

breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

class SkillNormalizer:
    def __init__(self, api_key: str = None, api_url: str = None):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.api_url = api_url or settings.DEEPSEEK_API_URL
        self.canonical_map = {
            "питон" : "Python",
            "python3" : "Python",
            "джанго" : "Django",
            "fastapi" : "FastAPI",
            "джава" : "Java",
            "js" : "JavaScript",
            "sql" : "SQL",
        }
        
    # Формирует промпт для нормализации названия навыка
    def _build_prompt(self, raw_name: str) -> str:
        return f"""Приведи название навыка к стандартному каноническому виду (например, "Python", "Django", "PostgreSQL"). Верни только одно нормализованное название, без кавычек и дополнительных комментариев. Исходное название: {raw_name}"""


    # Вспомогательный метод для вызова API, который может выбросить исключение при неудаче HTTP-запроса
    @breaker
    # Ретрай для вызова API при неудаче HTTP-запроса (3 попытки, экспоненциальная задержка от 2 секунд)
    @retry (
            stop = stop_after_attempt(3),
            wait = wait_exponential(multiplier=1, min=2, max=10),
            retry = retry_if_exception_type(requests.exceptions.RequestException)
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
            "max_tokens": 50
        }
        # Вызов API для получения нормализованного названия навыка, обработка ошибок HTTP-запросов
        response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content'].strip()
    
    # def _canonicalize(self, name : str) -> str:
    #     lower = name.lower()
    #     if lower in self.canonical_map:
    #         return self.canonical_map[lower]
    #     # Если нет в словаре, просто приводим первую букву к заглавной
    #     return name.capitalize()
        
    # Вызывает API для нормализации названия навыка, обрабатывает ошибки и возвращает нормализованное название
    # если навык не был приведён к каноническому виду с помощью словаря или не был изъят из кэша
    def normalize(self, raw_name: str) -> str:
        if not raw_name or not raw_name.strip():
            return ''
        
        lower_name = raw_name.lower()
        
        # Попытка привести с использованием словаря
        if lower_name in self.canonical_map:
            logger.debug(f"Dictionary hit for '{raw_name}'")
            return self.canonical_map[lower_name]
        
        # Обращение к кэшу
        cache_key = f"skill_norm:{lower_name}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for '{raw_name}' -> '{cached}'")
            return cached

        # Обращение к LLM
        logger.info(f"Calling LLM for: '{raw_name}'")
        try:
            prompt = self._build_prompt(raw_name)
            normalized = self._call_api(prompt)
            # Удаляем кавычки и лишние символы, если они есть
            normalized = re.sub(r'^[\'"]+|[\'"]+$', '', normalized).rstrip('.')
            logger.debug(f"Normalized '{raw_name}' to '{normalized}'")
            cache.set(cache_key, normalized, timeout=60*60*24*7)
            return normalized
        except Exception as e:
            logger.error(f"Error normalizing skill '{raw_name}': {e}")
            return raw_name.strip().capitalize()
    
    # Получает или создаёт навык в БД по нормализованному названию навыка, возвращает объект Skill
    def get_or_create_skill(self, raw_skill_name: str) -> Skill:
        normalized_name = self.normalize(raw_skill_name)
        if not normalized_name:
            logger.warning(f"Normalized skill name is empty for raw name '{raw_skill_name}'")
            return None
        skill, created = SkillRepository.get_or_create(name=normalized_name)
        if created:
            logger.info(f"Created new skill: {normalized_name}")
        return skill
    