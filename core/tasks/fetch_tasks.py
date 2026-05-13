from celery import shared_task
from core.models import JobTarget
from core.services.vacancy_fetcher import VacancyFetcher
import logging
from django.conf import settings


logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, time_limit=600)
def fetch_vacancies(self, job_titles=None, region_code=None):
    if job_titles is None:
        job_titles = list(JobTarget.objects.filter(is_active=True).values_list('name', flat=True))
    if not job_titles:
        logger.warning("No job titles to fetch.")
        return 0

    logger.info(f"Fetching vacancies for {len(job_titles)} job titles")

    try:
        if region_code is None:
            region_code = getattr(settings, 'DEFAULT_REGION_CODE', None)
        fetcher = VacancyFetcher(job_titles=job_titles, region_code=region_code)
        saved_count = fetcher.fetch_and_save()
        logger.info(f"Saved {saved_count} new vacancies")
        return saved_count
    except Exception as e:
        logger.error(f"Failed to fetch vacancies: {e}")
        raise self.retry(exc=e, countdown=60)
