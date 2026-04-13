from datetime import datetime, timezone
import requests
import time
import logging
import pybreaker
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, wait_fixed

from core.repository import VacancyRepository, VacancySkillRepository
from core.services.cache_manager import VacancyCache
from core.services.skill_normalizer import SkillNormalizer
from core.services.skill_extractor import SkillExtractor


logger = logging.getLogger(__name__)

breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

class HHVacancyFetcher:
    BASE_URL = "https://api.hh.ru/vacancies"
    PER_PAGE = 100
    MAX_PAGES = 10

    def __init__(self, job_titles: List[str], region_code: int = None):
        self.job_titles = job_titles
        self.region_code = region_code
    
    # Формирование очереди к hh из наименований должностей из таблицы JobTarget
    def _build_query(self) -> str:
        if not self.job_titles:
            return ''
        return ' OR '.join(f'"{title}"' for title in self.job_titles)
    
    # Параметры для запросов к hh: очередь наименований должностей, кол-во страниц и вакансий на их,
    # порядок расстановки вакансий и предпочтительный регион отбора вакансий
    def _prepare_params(self, page: int) -> Dict[str, Any]:
        params = {
            'text' : self._build_query(),
            'per_page' : self.PER_PAGE,
            'page' : page,
            'order_by' : 'publication_time',
        }
        if self.region_code:
            params['area'] = self.region_code
        return params
    

    # Обрабатывает одну страницу, формирует ошибки HTTP-запросов
    @breaker
    # Логика ретраев: 3 ретрая от 2 секунд
    @retry( 
        stop = stop_after_attempt(3), 
        wait = wait_exponential(multiplier=1, min=2, max=10), 
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )
    def _fetch_page(self, page: int) -> Dict[str, Any]:
        params = self._prepare_params(page)
        logger.debug(f"Fetching hh.ru page {page} with params {params}")
        response = requests.get(self.BASE_URL, params=params, timeout = 15)
        response.raise_for_status()
        return response.json()
    
    # Собирает данные вакансий с 10 страниц по 100 вакансий на страницу и запихивает в список словарей all_vacancies
    def _fetch_all(self, max_pages: int = MAX_PAGES) -> List[Dict[str, Any]]:
        all_vacancies = []
        for current_page in range(max_pages):
            try:
                data = self._fetch_page(current_page)
                items = data.get('items', [])
                if not items:
                    break
                all_vacancies.extend(items)
                total_pages = data.get('pages', max_pages)
                if current_page + 1 >= total_pages:
                    break
                logger.info(f"Fetched {len(items)} vacancies from page {current_page}")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Failed to fetch page {current_page}: {e}")
                break
        logger.info(f"Total fetched {len(all_vacancies)} vacancies from hh.ru")
        return all_vacancies

    # Сбор вакансий и сохранение их в БД
    def fetch_and_save(self):
        try:
            vacancies_data = self._fetch_all()
        except Exception as e:
            logger.error(f"HH API failed: {e}")
            vacancies_data = VacancyCache.get()
            if not vacancies_data:
                logger.warning("No cached vacancies available")
                return 0
            logger.info(f"Using cached vacancies ({len(vacancies_data)})")

        if not vacancies_data:
            logger.warning("No vacancies fetched from hh.ru")
            return 0
        
        saved_count = 0
        skill_extractor = SkillExtractor()
        skill_normalizer = SkillNormalizer()

        for vacancy in vacancies_data:
            try:
                # Преобразование строки в объект datetime, учитывая возможное отсутствие поля published_at
                published_at_str = vacancy.get('published_at')
                published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00')) if published_at_str else timezone.now()

                area = vacancy.get('area')
                region = area.get('name', '') if isinstance(area, dict) else ''

                vacancy_data = {
                        'id_vacancy' : vacancy.get('id'),
                        'title' : vacancy.get('name'),
                        'published_at' : published_at,
                        'company' : vacancy.get('employer', {}).get('name', ''),
                        'source' : 'hh.ru',
                        'region' : region,
                    }
                vac_object, created = VacancyRepository.get_or_create(**vacancy_data)

                if created:
                    saved_count += 1

                    # Логика извлечения и сохранения навыков из описания вакансии через SkillExtractor и SkillNormalizer  
                    full_data = self._fetch_full_vacancy(vacancy.get('id'))
                    description = full_data.get('description', '')
                    if description:
                        try:
                            skills_raw = skill_extractor.extract(description)

                            # Нормалайзер принимает строку, а не список, поэтому нормализуем по одному навыку и сохраняем в БД
                            # Нормалайзер сохраняет навык в Skills, сборщик сохраняет связь между вакансией и навыком в VacancySkill
                            for skill_name in skills_raw:
                                skill = skill_normalizer.get_or_create_skill(skill_name)
                                if skill:
                                    VacancySkillRepository.get_or_create(vacancy=vac_object, skill=skill)
                        except Exception as e:
                            logger.error(f"DeepSeek failed for vacancy {vacancy.get('id')}: {e}")
                            skills_raw = []

                    vac_object.description = description
                    vac_object.save(update_fields=['description'])

                else:
                    logger.debug(f"Vacancy {vacancy_data['id_vacancy']} already exists in the database")

            except Exception as e:
                logger.error(f"Failed to save vacancy {vacancy.get('id')}: {e}")

        logger.info(f"Total saved {saved_count} vacancies to the database and cached {len(vacancies_data)} vacancies")
        VacancyCache.save(vacancies_data)
        return saved_count
    
    @breaker
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1)
    )
    def _fetch_full_vacancy(self, vacancy_id: str) -> Dict[str, Any]:
        url = f"https://api.hh.ru/vacancies/{vacancy_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
