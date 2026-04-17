from datetime import datetime, timezone
from django.core.cache import cache
import requests
import time
import concurrent.futures
import logging
import pybreaker
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, wait_fixed

from core.models import JobTarget, Vacancy
from core.repository import VacancyRepository, VacancySkillRepository
from core.services.cache_manager import VacancyCache
from core.services.skill_normalizer import SkillNormalizer
from core.services.skill_extractor import SkillExtractor
from core.services.prerequisite_extractor import PrerequisiteExtractor


logger = logging.getLogger(__name__)

breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

class HHVacancyFetcher:
    BASE_URL = "https://api.hh.ru/vacancies"
    PER_PAGE = 100
    MAX_PAGES = 2

    def __init__(self, job_titles: List[str] = None, region_code: int = None):
        if job_titles is None:
            self.job_titles = self._get_active_job_titles()
        else:
            self.job_titles = job_titles
        self.region_code = region_code

    @staticmethod
    def _get_active_job_titles() -> List[str]:
        """Возвращает список названий активных целей из таблицы JobTarget. Временная реализация"""
        return list(JobTarget.objects.filter(is_active=True).values_list('name', flat=True))
    
    # Формирование очереди к hh из наименований должностей из таблицы JobTarget
    def _build_query(self) -> str:
        if not self.job_titles:
            return ''
        queries = [f'{title}' for title in self.job_titles]
        return ' OR '.join(queries)
    

    def _prepare_params(self, page: int) -> Dict[str, Any]:
        params = {
            'text': self._build_query(),         # поисковый запрос
            'search_field': 'name',              # ключевой параметр - ищем по наименованию вакансии
            'per_page': self.PER_PAGE,
            'page': page,
            'order_by': 'publication_time',
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
        headers = {'User-Agent': 'EduFlowBot/1.0 (soniazaitceva@gmail.com)'}
        response = requests.get(self.BASE_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    
    # Собирает данные вакансий с 1 страниц по 50 вакансий на страницу и запихивает в список словарей all_vacancies
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
        prereq_extractor = PrerequisiteExtractor()

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
                        logger.info(f"Extracting skills for vacancy '{vac_object.title}' (ID: {vac_object.id_vacancy})")
                        try:
                            skills_raw = skill_extractor.extract(description)

                            # Нормалайзер принимает строку, а не список, поэтому нормализуем по одному навыку и сохраняем в БД
                            # Нормалайзер сохраняет навык в Skills, сборщик сохраняет связь между вакансией и навыком в VacancySkill
                            normalized_skills = []
                            for skill_name in skills_raw:
                                skill = skill_normalizer.get_or_create_skill(skill_name)
                                if skill:
                                    logger.info(f"Linking skill '{skill.name}' to vacancy '{vac_object.title}'")
                                    normalized_skills.append(skill)
                                    VacancySkillRepository.get_or_create(vacancy=vac_object, skill=skill)

                            # Логика извлечения пререквизитов
                            if normalized_skills:
                                # skills_subset = normalized_skills[:10] # компромис между полнотой таблицы пререквизитов и скоростью сбора вакансий
                                prereq_extractor.extract_and_save_prerequisites(normalized_skills)

                            vac_object.description = description
                                
                            
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
    
    # @breaker
    # @retry(
    #     stop=stop_after_attempt(2),
    #     wait=wait_fixed(1)
    # )
    # def _fetch_full_vacancy(self, vacancy_id: str) -> Dict[str, Any]:
    #     url = f"https://api.hh.ru/vacancies/{vacancy_id}"
    #     response = requests.get(url, timeout=10)
    #     response.raise_for_status()
    #     return response.json()
    
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

        # 1. Определяем, какие вакансии уже есть в БД (чтобы не запрашивать их описание)
        existing_ids = set(Vacancy.objects.filter(
            id_vacancy__in=[v['id'] for v in vacancies_data]
        ).values_list('id_vacancy', flat=True))

        # 2. Разделяем на новые и существующие
        new_vacancies = [v for v in vacancies_data if v['id'] not in existing_ids]
        existing_vacancies = [v for v in vacancies_data if v['id'] in existing_ids]

        logger.info(f"New vacancies: {len(new_vacancies)}, already exist: {len(existing_vacancies)}")

        saved_count = 0
        skill_extractor = SkillExtractor()
        skill_normalizer = SkillNormalizer()
        prereq_extractor = PrerequisiteExtractor()

        MAX_CONCURRENT = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
            future_to_vacancy = {
                executor.submit(self._fetch_full_vacancy_with_cache, vacancy['id']): vacancy
                for vacancy in new_vacancies
            }

            for future in concurrent.futures.as_completed(future_to_vacancy):
                vacancy = future_to_vacancy[future]
                try:
                    full_data = future.result()
                except Exception as e:
                    logger.error(f"Failed to fetch full data for {vacancy['id']}: {e}")
                    continue

                # Сохраняем вакансию (она точно новая, т.к. мы отобрали только new_vacancies)
                published_at_str = vacancy.get('published_at')
                published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00')) if published_at_str else timezone.now()
                area = vacancy.get('area')
                region = area.get('name', '') if isinstance(area, dict) else ''

                vacancy_data = {
                    'id_vacancy': vacancy['id'],
                    'title': vacancy['name'],
                    'published_at': published_at,
                    'company': vacancy.get('employer', {}).get('name', ''),
                    'source': 'hh.ru',
                    'region': region,
                }
                vac_object, created = VacancyRepository.get_or_create(**vacancy_data)
                if not created:
                    # На всякий случай, но по логике created всегда True
                    continue

                saved_count += 1
                description = full_data.get('description', '')

                # Сохраняем описание сразу (даже если потом ошибка с навыками)
                if description:
                    vac_object.description = description
                    vac_object.save(update_fields=['description'])
                else:
                    logger.warning(f"No description for vacancy {vacancy['id']}")

                # Извлечение навыков – не критично, ошибки не должны ломать сохранение вакансии
                if description:
                    try:
                        skills_raw = skill_extractor.extract(description)
                        normalized_skills = []
                        for skill_name in skills_raw:
                            skill = skill_normalizer.get_or_create_skill(skill_name)
                            if skill:
                                normalized_skills.append(skill)
                                VacancySkillRepository.get_or_create(vacancy=vac_object, skill=skill)
                        if normalized_skills:
                            prereq_extractor.extract_and_save_prerequisites(normalized_skills)
                    except Exception as e:
                        logger.error(f"DeepSeek failed for vacancy {vacancy['id']}: {e}")

        logger.info(f"Total saved {saved_count} new vacancies, cached {len(vacancies_data)} vacancies")
        VacancyCache.save(vacancies_data)
        return saved_count

    def _fetch_full_vacancy_with_cache(self, vacancy_id: str):
        cache_key = f"hh_full_{vacancy_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        data = self._fetch_full_vacancy_api(vacancy_id)   # реальный запрос
        cache.set(cache_key, data, timeout=60*60*24*7)
        return data

    @breaker
    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
    def _fetch_full_vacancy_api(self, vacancy_id: str) -> Dict[str, Any]:
        url = f"https://api.hh.ru/vacancies/{vacancy_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()