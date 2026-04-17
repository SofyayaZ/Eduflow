import pytest
from unittest.mock import Mock, patch, call
from requests.exceptions import ConnectionError, RequestException
from tenacity import RetryError
from datetime import datetime, timezone

from core.models import Skill, Vacancy
from core.services.vacancy_fetcher import HHVacancyFetcher
from core.repository import VacancyRepository, VacancySkillRepository
from core.services.cache_manager import VacancyCache
from core.services.skill_normalizer import SkillNormalizer
from core.services.skill_extractor import SkillExtractor
from core.services.prerequisite_extractor import PrerequisiteExtractor


# Фикстура для создания экземпляра HHVacancyFetcher
@pytest.fixture
def hh_fetcher():
    return HHVacancyFetcher(job_titles=['Python developer'], region_code=1)


# ------------------- Тесты для _build_query -------------------
def test_build_query():
    fetcher = HHVacancyFetcher(job_titles=['Python developer', 'Data scientist'])
    assert fetcher._build_query() == 'Python developer OR Data scientist'

def test_build_query_empty():
    fetcher = HHVacancyFetcher(job_titles=[])
    assert fetcher._build_query() == ''


# ------------------- Тесты для _prepare_params -------------------
def test_prepare_params_without_region():
    fetcher = HHVacancyFetcher(job_titles=['Python'])
    params = fetcher._prepare_params(page=3)
    assert params == {
        'text': 'Python',
        'per_page': 50,
        'page': 3,
        'order_by': 'publication_time',
        'search_field': 'name'
    }
    assert 'area' not in params

def test_prepare_params_with_region():
    fetcher = HHVacancyFetcher(job_titles=['Java'], region_code=2)
    params = fetcher._prepare_params(page=0)
    assert params['text'] == 'Java'
    assert params['area'] == 2
    assert params['page'] == 0
    assert params['search_field'] == 'name'


# ------------------- Тесты для _fetch_page -------------------
@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_page_success(mock_get, hh_fetcher):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'items': [{'id': '1'}], 'found': 1}
    mock_get.return_value = mock_response

    data = hh_fetcher._fetch_page(0)
    assert data['found'] == 1
    assert len(data['items']) == 1
    mock_get.assert_called_once()

@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_page_retry_on_failure(mock_get, hh_fetcher):
    # Первый вызов – ошибка соединения, второй – успех
    mock_get.side_effect = [
        ConnectionError("Network error"),
        Mock(status_code=200, json=lambda: {'items': []})
    ]
    data = hh_fetcher._fetch_page(0)
    assert data['items'] == []
    assert mock_get.call_count == 2

@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_page_passes_correct_params(mock_get, hh_fetcher):
    mock_response = Mock(status_code=200, json=lambda: {'items': []})
    mock_get.return_value = mock_response

    hh_fetcher._fetch_page(5)
    args, kwargs = mock_get.call_args
    assert args[0] == 'https://api.hh.ru/vacancies'
    assert kwargs['params']['text'] == 'Python developer'
    assert kwargs['params']['area'] == 1
    assert kwargs['params']['page'] == 5
    assert kwargs['params']['per_page'] == 50
    assert kwargs['params']['search_field'] == 'name'
    assert kwargs['timeout'] == 15

@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_page_raises_retry_error_after_all_attempts(mock_get, hh_fetcher):
    mock_get.side_effect = ConnectionError()
    with pytest.raises(RetryError):
        hh_fetcher._fetch_page(0)
    # По умолчанию retry: stop_after_attempt(3)
    assert mock_get.call_count == 3


# ------------------- Тесты для _fetch_all -------------------
@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
def test_fetch_all_stops_when_items_empty(mock_fetch_page, mock_sleep, hh_fetcher):
    mock_fetch_page.side_effect = [
        {'items': [{'id': 1}], 'pages': 3},
        {'items': [], 'pages': 3}
    ]
    result = hh_fetcher._fetch_all(max_pages=5)
    assert len(result) == 1
    assert mock_fetch_page.call_count == 2
    mock_sleep.assert_called_once_with(1)

@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
def test_fetch_all_respects_max_pages(mock_fetch_page, mock_sleep, hh_fetcher):
    mock_fetch_page.side_effect = [
        {'items': [{'id': i}], 'pages': 10} for i in range(1, 4)
    ]
    result = hh_fetcher._fetch_all(max_pages=2)
    assert len(result) == 2
    assert mock_fetch_page.call_count == 2
    assert mock_sleep.call_count == 2

@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
def test_fetch_all_stops_on_api_page_limit(mock_fetch_page, mock_sleep, hh_fetcher):
    # API сообщает, что всего 2 страницы
    mock_fetch_page.side_effect = [
        {'items': [{'id': 1}], 'pages': 2},
        {'items': [{'id': 2}], 'pages': 2},
        {'items': [{'id': 3}], 'pages': 2}  # не должна вызываться
    ]
    result = hh_fetcher._fetch_all(max_pages=5)
    assert len(result) == 2
    assert mock_fetch_page.call_count == 2

@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
def test_fetch_all_handles_exception_on_page(mock_fetch_page, mock_sleep, hh_fetcher):
    mock_fetch_page.side_effect = [
        {'items': [{'id': 1}], 'pages': 3},
        Exception("API error"),
        {'items': [{'id': 3}], 'pages': 3}
    ]
    result = hh_fetcher._fetch_all(max_pages=3)
    assert len(result) == 1
    assert mock_fetch_page.call_count == 2
    mock_sleep.assert_called_once_with(1)


# ------------------- Тесты для _fetch_full_vacancy_api -------------------
@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_full_vacancy_api_success(mock_get, hh_fetcher):
    mock_response = Mock(status_code=200)
    mock_response.json.return_value = {'id': '123', 'description': 'Test description'}
    mock_get.return_value = mock_response

    result = hh_fetcher._fetch_full_vacancy_api('123')
    assert result['description'] == 'Test description'
    mock_get.assert_called_once_with('https://api.hh.ru/vacancies/123', timeout=10)

@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_full_vacancy_api_retry_on_failure(mock_get, hh_fetcher):
    mock_get.side_effect = [
        RequestException("Timeout"),
        Mock(status_code=200, json=lambda: {'id': '123'})
    ]
    result = hh_fetcher._fetch_full_vacancy_api('123')
    assert result['id'] == '123'
    assert mock_get.call_count == 2


# ------------------- Тесты для _fetch_full_vacancy_with_cache -------------------
@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch.object(HHVacancyFetcher, '_fetch_full_vacancy_api')
def test_fetch_full_vacancy_with_cache_miss(mock_api, mock_cache_set, mock_cache_get, hh_fetcher):
    mock_cache_get.return_value = None
    expected_data = {'description': 'fresh'}
    mock_api.return_value = expected_data

    result = hh_fetcher._fetch_full_vacancy_with_cache('v1')
    assert result == expected_data
    mock_cache_get.assert_called_once_with('hh_full_v1')
    mock_api.assert_called_once_with('v1')
    mock_cache_set.assert_called_once_with('hh_full_v1', expected_data, timeout=60*60*24*7)

@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch.object(HHVacancyFetcher, '_fetch_full_vacancy_api')
def test_fetch_full_vacancy_with_cache_hit(mock_api, mock_cache_set, mock_cache_get, hh_fetcher):
    cached_data = {'description': 'cached desc'}
    mock_cache_get.return_value = cached_data

    result = hh_fetcher._fetch_full_vacancy_with_cache('v2')
    assert result == cached_data
    mock_cache_get.assert_called_once_with('hh_full_v2')
    mock_api.assert_not_called()
    mock_cache_set.assert_not_called()


# ------------------- Тесты для fetch_and_save -------------------
@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch.object(HHVacancyFetcher, '_fetch_all')
@patch.object(VacancyCache, 'save')
@patch.object(VacancyCache, 'get')
@patch('core.services.vacancy_fetcher.PrerequisiteExtractor')
@patch('core.services.vacancy_fetcher.SkillNormalizer')
@patch('core.services.vacancy_fetcher.SkillExtractor')
@patch.object(HHVacancyFetcher, '_fetch_full_vacancy_with_cache')
@patch('core.repository.VacancyRepository.get_or_create')
@patch('core.repository.VacancySkillRepository.get_or_create')
@patch('core.models.Vacancy.objects.filter')
def test_fetch_and_save_new_vacancies(
    mock_vacancy_filter, mock_vacancy_skill_repo, mock_vacancy_repo, mock_fetch_full_cache,
    mock_skill_extractor_cls, mock_skill_normalizer_cls, mock_prereq_extractor_cls,
    mock_cache_get, mock_cache_save, mock_fetch_all, mock_cache_set, mock_cache_get_global,
    hh_fetcher
):
    vacancies_data = [
        {'id': 'v1', 'name': 'Python Dev', 'published_at': '2024-01-01T00:00:00Z',
         'area': {'name': 'Moscow'}, 'employer': {'name': 'Company'}},
        {'id': 'v2', 'name': 'Java Dev', 'published_at': '2024-01-02T00:00:00Z',
         'area': {'name': 'SPb'}, 'employer': {'name': 'Company2'}}
    ]
    mock_fetch_all.return_value = vacancies_data

    # Мокаем Vacancy.objects.filter – возвращаем плоский список существующих id
    mock_queryset = Mock()
    mock_queryset.values_list.return_value = ['v2']   # <-- плоский список
    mock_vacancy_filter.return_value = mock_queryset

    vac_obj1 = Mock(id_vacancy='v1', title='Python Dev')
    mock_vacancy_repo.return_value = (vac_obj1, True)
    mock_fetch_full_cache.return_value = {'description': 'Full description with Python, Django'}

    # ... остальные моки (экстракторы, нормалайзеры) ...
    mock_extractor = Mock()
    mock_extractor.extract.return_value = ['python', 'django']
    mock_skill_extractor_cls.return_value = mock_extractor

    mock_normalizer = Mock()
    skill_python = Mock()
    skill_django = Mock()
    mock_normalizer.get_or_create_skill.side_effect = [skill_python, skill_django]
    mock_skill_normalizer_cls.return_value = mock_normalizer

    mock_prereq_extractor = Mock()
    mock_prereq_extractor_cls.return_value = mock_prereq_extractor

    saved_count = hh_fetcher.fetch_and_save()

    assert saved_count == 1
    mock_vacancy_repo.assert_called_once()
    mock_fetch_full_cache.assert_called_once_with('v1')

@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch.object(HHVacancyFetcher, '_fetch_all')
@patch.object(VacancyCache, 'save')
@patch.object(VacancyCache, 'get')
@patch('core.models.Vacancy.objects.filter')
def test_fetch_and_save_uses_cache_when_fetch_all_fails(
    mock_vacancy_filter, mock_cache_get, mock_cache_save, mock_fetch_all, mock_cache_set, mock_cache_get_global, hh_fetcher
):
    mock_fetch_all.side_effect = Exception("API down")
    cached_vacancies = [
        {'id': 'cached1', 'name': 'Cached', 'published_at': '2024-01-01T00:00:00Z', 
         'area': {'name': 'City'}, 'employer': {'name': 'Emp'}}
    ]
    mock_cache_get.return_value = cached_vacancies

    mock_vacancy_filter.return_value.values_list.return_value = []

    with patch('core.repository.VacancyRepository.get_or_create') as mock_repo:
        vac_obj = Mock()
        mock_repo.return_value = (vac_obj, True)
        with patch.object(HHVacancyFetcher, '_fetch_full_vacancy_with_cache') as mock_full:
            mock_full.return_value = {'description': ''}
            with patch('core.services.vacancy_fetcher.SkillExtractor') as mock_ext_cls:
                mock_ext_cls.return_value.extract.return_value = []
                saved_count = hh_fetcher.fetch_and_save()

    assert saved_count == 1
    mock_fetch_all.assert_called_once()
    mock_cache_get.assert_called_once()
    mock_cache_save.assert_called_once_with(cached_vacancies)

@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch.object(HHVacancyFetcher, '_fetch_all')
@patch.object(VacancyCache, 'get')
def test_fetch_and_save_returns_0_when_no_vacancies(
    mock_cache_get, mock_fetch_all, mock_cache_set, mock_cache_get_global, hh_fetcher
):
    mock_fetch_all.return_value = []
    saved_count = hh_fetcher.fetch_and_save()
    assert saved_count == 0
    mock_cache_get.assert_not_called()

@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch.object(HHVacancyFetcher, '_fetch_all')
@patch.object(VacancyCache, 'save')
@patch('core.models.Vacancy.objects.filter')
def test_fetch_and_save_handles_error_in_skill_extraction(
    mock_vacancy_filter, mock_cache_save, mock_fetch_all, mock_cache_set, mock_cache_get_global, hh_fetcher
):
    vacancies_data = [
        {'id': 'v1', 'name': 'Dev', 'published_at': '2024-01-01T00:00:00Z', 
         'area': {'name': 'Msk'}, 'employer': {'name': 'Emp'}}
    ]
    mock_fetch_all.return_value = vacancies_data
    # Нет существующих вакансий
    mock_vacancy_filter.return_value.values_list.return_value = []

    with patch('core.repository.VacancyRepository.get_or_create') as mock_repo:
        vac_obj = Mock()
        mock_repo.return_value = (vac_obj, True)
        with patch.object(HHVacancyFetcher, '_fetch_full_vacancy_with_cache') as mock_full:
            mock_full.return_value = {'description': 'some description'}
            with patch('core.services.vacancy_fetcher.SkillExtractor') as mock_ext_cls:
                mock_ext_cls.return_value.extract.side_effect = Exception("LLM error")
                saved_count = hh_fetcher.fetch_and_save()

    assert saved_count == 1
    # Описание должно быть сохранено несмотря на ошибку
    vac_obj.save.assert_called_once_with(update_fields=['description'])
    mock_cache_save.assert_called_once_with(vacancies_data)

@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch.object(HHVacancyFetcher, '_fetch_all')
@patch.object(VacancyCache, 'save')
@patch('core.repository.VacancyRepository.get_or_create')
@patch('core.models.Vacancy.objects.filter')
@patch.object(HHVacancyFetcher, '_fetch_full_vacancy_with_cache')
def test_fetch_and_save_skips_vacancy_when_full_data_fetch_fails(
    mock_fetch_full, mock_vacancy_filter, mock_vacancy_repo,
    mock_cache_save, mock_fetch_all, mock_cache_set, mock_cache_get_global,
    hh_fetcher
):
    vacancies_data = [
        {'id': 'v1', 'name': 'Dev', 'published_at': '2024-01-01T00:00:00Z',
         'area': {'name': 'Msk'}, 'employer': {'name': 'Emp'}}
    ]
    mock_fetch_all.return_value = vacancies_data
    # мокаем filter, чтобы он не лез в БД
    mock_vacancy_filter.return_value.values_list.return_value = []
    # мокаем метод, который делает запрос к HH – выбрасываем исключение
    mock_fetch_full.side_effect = Exception("Network error")

    # Вызываем метод
    saved_count = hh_fetcher.fetch_and_save()

    assert saved_count == 0
    # get_or_create не должен вызываться, так как full_data не получено
    mock_vacancy_repo.assert_not_called()
    # Кэш всё равно сохраняется (список вакансий без описаний)
    mock_cache_save.assert_called_once_with(vacancies_data)


# ------------------- Тест на параллельность (проверяет использование ThreadPoolExecutor) -------------------
@patch('time.sleep', return_value=None)                     # подавляем любые задержки
@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch.object(HHVacancyFetcher, '_fetch_all')
@patch('concurrent.futures.ThreadPoolExecutor')
@patch('core.models.Vacancy.objects.filter')
@patch('core.services.cache_manager.VacancyCache.save')    # мок для сохранения кэша
def test_fetch_and_save_uses_thread_pool(
    mock_cache_save,           # от VacancyCache.save
    mock_vacancy_filter,       # от Vacancy.objects.filter
    mock_executor_cls,         # от ThreadPoolExecutor
    mock_fetch_all,            # от _fetch_all
    mock_cache_set,            # от django cache.set
    mock_cache_get_global,     # от django cache.get
    mock_sleep,                # от time.sleep
    hh_fetcher                 # фикстура
):
    vacancies_data = [
        {'id': 'v1', 'name': 'Dev1', 'published_at': '2024-01-01T00:00:00Z',
         'area': {'name': 'Msk'}, 'employer': {'name': 'Emp'}},
        {'id': 'v2', 'name': 'Dev2', 'published_at': '2024-01-02T00:00:00Z',
         'area': {'name': 'Msk'}, 'employer': {'name': 'Emp'}}
    ]
    mock_fetch_all.return_value = vacancies_data
    mock_vacancy_filter.return_value.values_list.return_value = []   # нет существующих вакансий

    # Мокаем ThreadPoolExecutor
    mock_executor = Mock()
    mock_executor.__enter__ = Mock(return_value=mock_executor)
    mock_executor.__exit__ = Mock()
    mock_executor.submit.return_value = Mock()
    mock_executor_cls.return_value = mock_executor

    with patch('core.repository.VacancyRepository.get_or_create') as mock_repo:
        mock_repo.return_value = (Mock(), True)   # вакансия создаётся
        with patch.object(HHVacancyFetcher, '_fetch_full_vacancy_with_cache') as mock_full:
            mock_full.return_value = {'description': ''}   # пустое описание
            with patch('core.services.vacancy_fetcher.SkillExtractor'):  # заглушка для экстрактора
                saved_count = hh_fetcher.fetch_and_save()

    # Проверки
    assert saved_count == 2   # обе вакансии новые
    assert mock_executor.submit.call_count == 2
    mock_executor.submit.assert_any_call(hh_fetcher._fetch_full_vacancy_with_cache, 'v1')
    mock_executor.submit.assert_any_call(hh_fetcher._fetch_full_vacancy_with_cache, 'v2')
    mock_cache_save.assert_called_once()   # кэш сохранился один раз


# ------------------- Интеграционный тест с реальными моками (без выхода в сеть) -------------------

# @patch('time.sleep', return_value=None)
# @patch.object(HHVacancyFetcher, '_fetch_all')
# @patch('django.core.cache.cache.get')
# @patch('django.core.cache.cache.set')
# @patch('core.models.Vacancy.objects.filter')
# @patch.object(HHVacancyFetcher, '_fetch_full_vacancy_with_cache')
# @patch('core.repository.VacancyRepository.get_or_create')
# @patch('core.repository.VacancySkillRepository.get_or_create')
# @patch('core.services.skill_extractor.SkillExtractor.extract')
# @patch('core.services.skill_normalizer.SkillNormalizer.get_or_create_skill')
# def test_fetch_and_save_integration_mocked_http(
#     mock_normalize, mock_extract, mock_skill_repo, mock_vacancy_repo,
#     mock_fetch_full_cache, mock_vacancy_filter, mock_cache_set, mock_cache_get_global,
#     mock_fetch_all, mock_sleep, hh_fetcher
# ):
#     mock_fetch_all.return_value = [
#         {'id': '123', 'name': 'Python Dev', 'published_at': '2025-01-01T00:00:00+03:00',
#          'employer': {'name': 'Company A'}, 'area': {'name': 'Moscow'}}
#     ]
#     mock_vacancy_filter.return_value.values_list.return_value = []   # нет существующих

#     vac_obj = Mock(id_vacancy='123', title='Python Dev')
#     mock_vacancy_repo.return_value = (vac_obj, True)

#     mock_fetch_full_cache.return_value = {'description': 'Need Python and Django skills'}

#     mock_extract.return_value = ['Python', 'Django']
#     skill1 = Mock(name='Python')
#     skill2 = Mock(name='Django')
#     mock_normalize.side_effect = [skill1, skill2]

#     saved = hh_fetcher.fetch_and_save()

#     assert saved == 1
#     mock_vacancy_repo.assert_called_once()
#     mock_extract.assert_called_once_with('Need Python and Django skills')
#     assert mock_normalize.call_count == 2
#     assert mock_skill_repo.call_count == 2
                    