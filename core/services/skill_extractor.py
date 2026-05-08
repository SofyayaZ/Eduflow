
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import List
from django.conf import settings
import pybreaker


logger = logging.getLogger(__name__)
breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

class SkillExtractor:
    def __init__(self, api_url : str = None, api_key : str = None):
        self.api_url = api_url or settings.DEEPSEEK_API_URL
        self.api_key = api_key or settings.DEEPSEEK_API_KEY

    def _build_prompt(self, text: str) -> str:
        return f"""Ты — эксперт по извлечению навыков из текстов вакансий. Твоя задача — выделить только конкретные, измеримые навыки (hard, soft или инструменты), а не общие области деятельности или должностные обязанности. Примеры хороших навыков:
                        Python, SQL, Docker, Kubernetes, Git, Pandas, Tableau, Коммуникация, Управление проектами, Аналитическое мышление.

                        Примеры плохих, общих формулировок (НЕ включай их):
                        анализ данных, машинное обучение, разработка ПО, работа с клиентами, ведение отчётности.
                        Правила:
                        - Возвращай только список через запятую.
                        - Не добавляй пояснений, не нумеруй.
                        - Если навык не является конкретным (например, это целая область), пропусти его.
                        - Извлекай только из явно указанных требований, а не из обязанностей.
                        Текст вакансии: {text}
                        Навыки (через запятую): """
    
    @breaker
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
            "max_tokens": 200
        }
        response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
        logger.info(f"Status: {response.status_code}, Response: {response.text}")
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
        

    def extract(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []  
        try:
            prompt = self._build_prompt(text)
            result = self._call_api(prompt)
            skills = [s.strip() for s in result.split(',') if s.strip()]
            logger.info(f"Extracted {len(skills)} skills from text: {skills}")
            return skills
        except Exception as e:
            logger.error(f"Error extracting skills from text: {e}")
            return []