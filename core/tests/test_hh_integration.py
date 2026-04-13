import pytest
import requests
from tenacity import RetryError
from core.services.vacancy_fetcher import HHVacancyFetcher
from unittest.mock import patch

# Проверка сбора вакансий hh на примере Data scientist и региона 1
@pytest.mark.django_db # это марка для тестов с БД
def test_fetch_vacancies_real_api():
    job_titles = ['Data scientist']
    fetcher = HHVacancyFetcher(job_titles=job_titles, region_code=1)
    vacancies = fetcher._fetch_all(max_pages=2)
    assert len(vacancies) > 0, "Вакансии не найдены"
    assert all('id' in v for v in vacancies), "Отсутствует поле id"
    assert all('name' in v for v in vacancies), "Отсутствует поле name"

# Проверка выпадения RetryError при отсутствии соединения
@pytest.mark.django_db
def test_fetch_vacancies_with_network_error():
    with patch('requests.get', side_effect=requests.ConnectionError("No connection")):
        fetcher = HHVacancyFetcher(job_titles=['Data scientist'])
        with pytest.raises(RetryError):
            fetcher._fetch_page(0)