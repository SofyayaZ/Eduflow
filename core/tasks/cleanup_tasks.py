from celery import shared_task
import logging

from core.repository import VacancyRepository

logger = logging.getLogger(__name__)


@shared_task
def delete_old_vacancies():
    deleted = VacancyRepository.delete_old_vacancies()
    logger.info(f"Deleted old vacancies: {deleted}")
    return deleted
