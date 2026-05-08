import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import pybreaker
import requests
from django.core.cache import cache
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    wait_fixed,
)

from core.models import JobTarget, Vacancy
from core.repository import VacancyRepository, VacancySkillRepository
from core.services.cache_manager import VacancyCache
from core.services.skill_normalizer import SkillNormalizer
from core.services.skill_extractor import SkillExtractor
from core.services.prerequisite_extractor import PrerequisiteExtractor

logger = logging.getLogger(__name__)
breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)


class VacancyFetcher:
    BASE_URL = "http://opendata.trudvsem.ru/api/v1/vacancies"
    PER_PAGE = 50       # максимальное количество на страницу согласно WADL  - 100
    MAX_PAGES = 1       # ограничим число страниц

    def __init__(self, region_code: str = None):
        self.job_titles = self._get_active_job_titles()
        self.region_code = region_code

    @staticmethod
    def _get_active_job_titles() -> List[str]:
        return list(JobTarget.objects.filter(is_active=True).values_list('name', flat=True))

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
        params = {
            'text': job_title,
            'limit': self.PER_PAGE,
            'offset': page * self.PER_PAGE,
        }
        if self.region_code:
            params['region'] = self.region_code
        return params

    @breaker
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )
    def _fetch_page(self, job_title: str, page: int) -> Dict[str, Any]:
        params = self._build_params(page, job_title)
        logger.debug(f"Запрос страницы {page} для '{job_title}' с параметрами {params}")
        headers = {'User-Agent': 'EduFlow/1.0 (contact@eduflow.ru)'}
        response = requests.get(self.BASE_URL, params=params, headers=headers, timeout=15)
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
                if len(vacancies_list) < self.PER_PAGE:
                    break
                time.sleep(2)  # снижена задержка (было 30)
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
        prereq_extractor = PrerequisiteExtractor()

        for title in self.job_titles:
            # Получаем объект JobTarget
            job_target = JobTarget.objects.filter(name=title).first()
            if not job_target:
                logger.warning(f"JobTarget с именем '{title}' не найден в БД")
                continue

            vacancies_raw = self._fetch_all_for_job_title(title)
            if not vacancies_raw:
                logger.warning(f"Не собрано вакансий для '{title}'")
                continue

            for vac_raw in vacancies_raw:
                inner = vac_raw.get('vacancy', vac_raw)
                vac_id = self._get_vacancy_id(vac_raw)
                if not vac_id:
                    continue

                # Проверяем, не существует ли уже вакансия с таким id (чтобы не дублировать между целями)
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
                    'job_target': job_target,   # <- связь с целью
                }
                vac_object, created = VacancyRepository.get_or_create(**vacancy_data)

                if not created:
                    logger.debug(f"Вакансия {vac_id} уже существует в БД, пропускаем")
                    continue

                saved_count += 1

                if description:
                    logger.info(f"Извлечение навыков для вакансии: {title}")
                    vac_object.description = description
                    vac_object.save(update_fields=['description'])
                    logger.debug(f"Для вакансии {vac_id} сохранено описание (длина {len(description)})")

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
                            prereq_extractor.extract_and_save_prerequisites(normalized_skills)
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
    