from django.core.cache import cache
from typing import List, Dict, Any

CACHE_KEY_VACANCIES = "latest_vacancies"
CACHE_TIMEOUT = 60 * 60 * 24  # 24 часа

class VacancyCache:
    @staticmethod
    def save(vacancies: List[Dict[str, Any]]):
        cache.set(CACHE_KEY_VACANCIES, vacancies, timeout=CACHE_TIMEOUT)

    @staticmethod
    def get() -> List[Dict[str, Any]]:
        return cache.get(CACHE_KEY_VACANCIES, [])

    @staticmethod
    def clear():
        cache.delete(CACHE_KEY_VACANCIES)
        