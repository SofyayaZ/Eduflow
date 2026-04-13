from celery import shared_task
from core.models import JobTarget
from core.services.vacancy_fetcher import HHVacancyFetcher
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, time_limit=600)
def fetch_vacancies_from_hh(self):
    active_jobs = JobTarget.objects.filter(is_active=True).values_list('name', flat=True)
    if not active_jobs:
        logger.warning("No active job targets. Skipping fetch.")
        return 0

    job_titles = list(active_jobs)
    logger.info(f"Fetching vacancies for {len(job_titles)} job titles")

    try:
        region_code = getattr(settings, 'HH_DEFAULT_REGION_CODE', None)
        fetcher = HHVacancyFetcher(job_titles=job_titles, region_code=region_code)
        saved_count = fetcher.fetch_and_save()
        logger.info(f"Saved {saved_count} new vacancies")
        return saved_count
    except Exception as e:
        logger.error(f"Failed to fetch vacancies: {e}")
        raise self.retry(exc=e, countdown=60)
