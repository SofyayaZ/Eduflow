import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import pybreaker
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from core.models import Vacancy
from core.repository import JobTargetRepository, VacancyRepository, VacancySkillRepository
from core.services.skill_normalizer import SkillNormalizer
from core.services.skill_extractor import SkillExtractor


logger = logging.getLogger(__name__)
breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)


class VacancyFetcher:
    BASE_URL = "http://opendata.trudvsem.ru/api/v1/vacancies"
    PER_PAGE = 100       # максимальное количество на страницу согласно WADL  - 100
    MAX_PAGES = 2        # ограничим число страниц

    def __init__(self, job_titles: List[str] = None, region_code: str = None):
        if job_titles is None:
            self.job_titles = self._get_active_job_titles()
        else:
            self.job_titles = job_titles
        self.region_code = region_code

    @staticmethod
    def _get_active_job_titles() -> List[str]:
        return list(JobTargetRepository.get_active().values_list('name', flat=True))

    @staticmethod
    def _get_vacancy_id(vac: Dict[str, Any]) -> Optional[str]:
        """Извлекает идентификатор вакансии из ответа API."""
        if 'id' in vac:
            return vac['id']
        if 'vacancy' in vac:
            inner = vac['vacancy']
            if '@id' in inner:
                # URL вида: http://.../vacancies/12345
                return inner['@id'].rstrip('/').split('/')[-1]
            if 'id' in inner:
                return inner['id']
        logger.warning(f"Не удалось извлечь ID из вакансии: {vac.keys()}")
        return None

    def _build_params(self, page: int, job_title: str) -> Dict[str, Any]:
        target = JobTargetRepository.get_by_name(name=job_title)
        params = {
            'text': job_title,   # точная фраза
            'limit': self.PER_PAGE,
            'offset': page * self.PER_PAGE,
        }
        if self.region_code:
            params['region'] = self.region_code
        return params
    
    def _build_url(self, job_title: str) -> str:
        """Формирует URL для запроса вакансий с учётом региона."""
        base_url = self.BASE_URL
        if self.region_code:
            # Добавляем код региона в путь URL
            url = f"{base_url}/region/{self.region_code}"
        else:
            url = base_url
        return url

    @breaker
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )
    def _fetch_page(self, job_title: str, page: int) -> Dict[str, Any]:
        params = {
            'text': job_title,
            'limit': self.PER_PAGE,
            'offset': page * self.PER_PAGE,
        }
        url = self._build_url(job_title)
        logger.debug(f"Запрос страницы {page} для '{job_title}': {url} с параметрами {params}")
        headers = {'User-Agent': 'EduFlow/1.0 (soniazaitceva@gmail.com)'}
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def _fetch_all_for_job_title(self, job_title: str) -> List[Dict[str, Any]]:
        all_items = []
        for page in range(self.MAX_PAGES):
            try:
                data = self._fetch_page(job_title, page)
                vacancies_list = data.get('results', {}).get('vacancies', [])
                logger.info(f"Страница {page} для '{job_title}': получено {len(vacancies_list)} вакансий")
                if not vacancies_list:
                    break
                all_items.extend(vacancies_list)
                time.sleep(30)
                if len(vacancies_list) < self.PER_PAGE:
                    break
            except Exception as e:
                logger.error(f"Ошибка при загрузке страницы {page} для '{job_title}': {e}")
                break
        logger.info(f"Всего собрано {len(all_items)} вакансий для '{job_title}'")
        return all_items

    def fetch_and_save(self) -> int:
        if not self.job_titles:
            logger.warning("Нет активных должностей для сбора вакансий")
            return 0

        saved_count = 0
        skill_extractor = SkillExtractor()
        skill_normalizer = SkillNormalizer()

        for title in self.job_titles:
            job_target = JobTargetRepository.get_by_name(name=title)
            if not job_target:
                logger.warning(f"JobTarget с именем '{title}' не найден в БД")
                continue

            search_queries = JobTargetRepository.get_search_queries(job_target)
            all_vacancies_raw = []
            seen_ids = set()

            for query in search_queries:
                vacancies_raw = self._fetch_all_for_job_title(query)
                for vac in vacancies_raw:
                    vac_id = self._get_vacancy_id(vac)
                    if vac_id and vac_id not in seen_ids:
                        seen_ids.add(vac_id)
                        all_vacancies_raw.append(vac)
                    
            if not all_vacancies_raw:
                logger.warning(f"Не собрано вакансий для '{title}'")
                continue

            # Фильтруем вакансии: оставляем только те, у которых название содержит title (без учёта регистра)
            filtered_vacancies = []
            for vac_raw in all_vacancies_raw:
                inner = vac_raw.get('vacancy', vac_raw)
                vac_title = inner.get('job-name')
                if self._matches_any_query(vac_title, search_queries):
                    filtered_vacancies.append(vac_raw)
                else:
                    logger.debug(f"Вакансия '{vac_title}' не соответствует профессии '{title}', пропускаем")

            logger.info(f"После фильтрации по названию осталось {len(filtered_vacancies)} вакансий из {len(vacancies_raw)}")

            for vac_raw in filtered_vacancies:
                inner = vac_raw.get('vacancy', vac_raw)
                vac_id = self._get_vacancy_id(vac_raw)
                if not vac_id:
                    continue
                if Vacancy.objects.filter(id_vacancy=vac_id).exists():
                    logger.debug(f"Вакансия {vac_id} уже существует, пропускаем")
                    continue

                title_vac = inner.get('job-name') or inner.get('profession') or 'Без названия'
                company = inner.get('company', {}).get('name', '')
                region = inner.get('region', {}).get('name', '')
                pub_date_str = inner.get('publication-date')
                published_at = self._parse_date(pub_date_str)
                description = inner.get('duty', '')

                vacancy_data = {
                    'id_vacancy': vac_id,
                    'title': title_vac,
                    'published_at': published_at,
                    'company': company,
                    'source': 'trudvsem',
                    'region': region,
                    'job_target': job_target,
                }
                vac_object, created = VacancyRepository.get_or_create(**vacancy_data)

                if not created:
                    logger.debug(f"Вакансия {vac_id} уже существует в БД, пропускаем")
                    continue

                saved_count += 1

                if description:
                    logger.info(f"Извлечение навыков для вакансии: {title_vac}")
                    vac_object.description = description
                    vac_object.save(update_fields=['description'])

                    try:
                        skills_raw = skill_extractor.extract(description)
                        logger.info(f"Извлечено навыков для вакансии {vac_id}: {len(skills_raw)} → {skills_raw}")

                        normalized_skills = []
                        for skill_name in skills_raw:
                            skill = skill_normalizer.get_or_create_skill(skill_name)
                            if skill:
                                normalized_skills.append(skill)
                                VacancySkillRepository.get_or_create(vacancy=vac_object, skill=skill)
                        if normalized_skills:
                            logger.info(f"Для вакансии {vac_id} нормализовано {len(normalized_skills)} навыков")
                    except Exception as e:
                        logger.error(f"Ошибка обработки навыков для вакансии {vac_id}: {e}")
                else:
                    logger.warning(f"Не удалось получить описание для вакансии {vac_id}")

        logger.info(f"Всего сохранено новых вакансий: {saved_count}")
        return saved_count

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        if not date_str:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            logger.warning(f"Не удалось распарсить дату: {date_str}")
            return datetime.now(timezone.utc)
        
    @staticmethod
    def _matches_any_query(vacancy_title: str, search_queries: List[str]) -> bool:
        if not vacancy_title:
            return False
        for query in search_queries:
            target_normalized = re.sub(r'[-/_.,]', ' ', query.lower())
            target_words = set(target_normalized.split())
            if not target_words:
                continue
            vacancy_normalized = re.sub(r'[-/_.,]', ' ', vacancy_title.lower())
            vacancy_words = set(vacancy_normalized.split())
            if target_words.issubset(vacancy_words):
                return True
        return False
    