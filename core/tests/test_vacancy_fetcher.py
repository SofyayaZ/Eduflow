import pytest
from unittest.mock import call, patch, Mock
from requests.exceptions import ConnectionError
from tenacity import RetryError
from core.services.vacancy_fetcher import HHVacancyFetcher


# Создаём мок ответа (200) на GET, проверяем, что запрос был вызван один раз
@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_page_success(mock_get, hh_fetcher):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'items': [{'id': '1', 'name': 'Test'}],
        'found': 1
    }
    mock_get.return_value = mock_response
    data = hh_fetcher._fetch_page(0)
    assert data['found'] == 1
    assert len(data['items']) == 1
    mock_get.assert_called_once()

# Проверка ретрая на ошибке соединения
@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_retry_on_failure(mock_get, hh_fetcher):
    mock_get.side_effect = [
        ConnectionError("Network error"), 
        Mock(status_code=200, json=lambda: {'items': []})
    ]
    data = hh_fetcher._fetch_page(0)
    assert data['items'] == []
    assert mock_get.call_count == 2

# Сбор данных с корректными параметрами
def test_fetch_page_passes_correct_params():
    with patch('core.services.vacancy_fetcher.requests.get') as mock_get:
        mock_get.return_value = Mock(status_code=200, json=lambda: {'items': []})
        fetcher = HHVacancyFetcher(job_titles=['Python developer'], region_code=1)
        fetcher._fetch_page(2)
        call_args = mock_get.call_args[1]['params']
        assert call_args['text'] == '"Python developer"'
        assert call_args['area'] == 1
        assert call_args['page'] == 2
        assert call_args['per_page'] == 100

# Проверка вызова sleep при ошибке соединения (все 3 раза)
def test_fetch_retry_uses_tenacity(hh_fetcher):
    with patch('core.services.vacancy_fetcher.requests.get') as mock_get:
        mock_get.side_effect = ConnectionError()  # будет вызван 3 раза
        with pytest.raises(RetryError):
            hh_fetcher._fetch_page(0)
        assert mock_get.call_count == 3

# Корректность подготовки параметров без региона
def test_prepare_params_without_region():
    fetcher = HHVacancyFetcher(job_titles=['Python', 'Django'])
    params = fetcher._prepare_params(page=3)
    assert params == {
        'text': '"Python" OR "Django"',
        'per_page': 100,
        'page': 3,
        'order_by': 'publication_time'
    }
    assert 'area' not in params

# Корректность подготовки параметров с регионом
def test_prepare_params_with_region():
    fetcher = HHVacancyFetcher(job_titles=['Java developer'], region_code=2)
    params = fetcher._prepare_params(page=0)
    assert params['text'] == '"Java developer"'
    assert params['area'] == 2
    assert params['page'] == 0

# Корректность параметров 
@patch('core.services.vacancy_fetcher.requests.get')
def test_fetch_page_calls_with_correct_params(mock_get):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'items': []}
    mock_get.return_value = mock_response

    fetcher = HHVacancyFetcher(job_titles=['DevOps engineer'], region_code=3)
    fetcher._fetch_page(5)
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0] == 'https://api.hh.ru/vacancies'
    assert kwargs['params']['text'] == '"DevOps engineer"'
    assert kwargs['params']['area'] == 3
    assert kwargs['params']['page'] == 5
    assert kwargs['timeout'] == 15

# Проверка остновки сбора данных на пустой странице
@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
def test_fetch_all_stops_when_items_empty(mock_fetch_page, mock_sleep, hh_fetcher):
    mock_fetch_page.side_effect = [
        {'items': [{'id': 1}, {'id': 2}], 'pages': 3},
        {'items': [], 'pages': 3}          # третья страница пустая 
    ]
    result = hh_fetcher._fetch_all(max_pages=5)
    assert len(result) == 2
    assert mock_fetch_page.call_count == 2 # только 2 страницы просмотрено
    mock_sleep.assert_called_once_with(1)  # один вызов


@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
def test_fetch_all_respects_max_pages(mock_fetch_page, mock_sleep, hh_fetcher):
    # Мокаем, что каждая страница возвращает один элемент и говорит, что всего страниц 10
    mock_fetch_page.side_effect = [
        {'items': [{'id': i}], 'pages': 10} for i in range(1, 6)
    ]
    result = hh_fetcher._fetch_all(max_pages=3)
    assert len(result) == 3
    assert mock_fetch_page.call_count == 3
    mock_sleep.assert_has_calls([call(1)] * 3)

# Проверка сбора с кол-ва страниц меньшего максимального числа страниц
@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
def test_fetch_all_stops_on_api_page_limit(mock_fetch_page, mock_sleep, hh_fetcher):
    # API говорит, что всего 2 страницы, но max_pages=5
    mock_fetch_page.side_effect = [
        {'items': [{'id': 1}], 'pages': 2},
        {'items': [{'id': 2}], 'pages': 2},
        {'items': [{'id': 3}], 'pages': 2}  # эта не должна быть вызвана
    ]
    result = hh_fetcher._fetch_all(max_pages=5)
    assert len(result) == 2
    assert mock_fetch_page.call_count == 2

# Проверка вызова исключения в методе _fetch_all
@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
def test_fetch_all_handles_exception_on_page(mock_fetch_page, mock_sleep, hh_fetcher):
    # Вторая страница вызывает исключение
    mock_fetch_page.side_effect = [
        {'items': [{'id': 1}], 'pages': 3},
        Exception("API error"),
        {'items': [{'id': 3}], 'pages': 3}  # не должна быть вызвана
    ]
    result = hh_fetcher._fetch_all(max_pages=3)
    # Должна быть только первая страница, на второй бросаем исключение и выходим
    assert len(result) == 1
    assert mock_fetch_page.call_count == 2
    # Проверяем, что sleep вызывался только для успешной страницы
    mock_sleep.assert_called_once_with(1)

# Проверка построения очереди из наименований должностей
def test_build_query():
    fetcher = HHVacancyFetcher(job_titles=['Python developer', 'Data scientist'])
    query = fetcher._build_query()
    assert query == '"Python developer" OR "Data scientist"'

# Проверка построения пустой очереди
def test_build_query_empty():
    fetcher = HHVacancyFetcher(job_titles=[])
    query = fetcher._build_query()
    assert query == ''