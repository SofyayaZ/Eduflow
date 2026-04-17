from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from core.services.vacancy_fetcher import HHVacancyFetcher
from django.utils import timezone

# Синхронный исполнитель для подмены ThreadPoolExecutor
class SyncExecutor:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def submit(self, fn, *args, **kwargs):
        future = MagicMock()
        future.result = lambda: fn(*args, **kwargs)
        return future

@patch('concurrent.futures.ThreadPoolExecutor', lambda max_workers: SyncExecutor())
@patch('django.core.cache.cache.get')          # <-- добавить
@patch('django.core.cache.cache.set')          # <-- добавить
@patch('core.services.cache_manager.VacancyCache.save')
@patch('core.services.cache_manager.VacancyCache.get')
@patch('core.services.vacancy_fetcher.VacancySkillRepository.get_or_create')
@patch('core.services.skill_normalizer.SkillNormalizer.get_or_create_skill')
@patch('core.repository.VacancyRepository.get_or_create')
@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
@patch.object(HHVacancyFetcher, '_fetch_full_vacancy_with_cache')
@patch('core.models.Vacancy.objects.filter')
def test_fetch_and_save_saves_vacancies_and_skills(
    mock_vacancy_filter, mock_fetch_full_vacancy, mock_fetch_page, mock_sleep,
    mock_vacancy_get_or_create, mock_normalizer_get_skill,
    mock_vacancy_skill_create, mock_cache_get, mock_cache_save,   # порядок важен
    mock_cache_set, mock_cache_get_global, mock_cache_set_global  # два последних – для django cache
):
    # Мокаем Vacancy.objects.filter – нет существующих вакансий
    mock_vacancy_filter.return_value.values_list.return_value = []

    # Данные от API (краткая информация)
    mock_fetch_page.return_value = {
        'items': [
            {
                'id': '123',
                'name': 'Python-разработчик',
                'published_at': '2025-01-01T10:00:00+03:00',
                'employer': {'name': 'Acme Inc'},
                'area': {'name': 'Moscow'},
            }
        ],
        'pages': 1
    }

    # Мокаем полное описание вакансии
    mock_fetch_full_vacancy.return_value = {
        'description': 'We need Python and Django'
    }

    # Мокаем создание вакансии
    mock_vacancy = Mock(id_vacancy='123')
    mock_vacancy_get_or_create.return_value = (mock_vacancy, True)

    # Мокаем нормализатор навыков
    mock_skill_python = Mock(name='Python')
    mock_skill_django = Mock(name='Django')
    def get_skill_side_effect(raw_name):
        if 'python' in raw_name.lower():
            return mock_skill_python
        elif 'django' in raw_name.lower():
            return mock_skill_django
        return None
    mock_normalizer_get_skill.side_effect = get_skill_side_effect

    # Запускаем
    fetcher = HHVacancyFetcher(job_titles=['Python'])
    saved_count = fetcher.fetch_and_save()
    assert saved_count == 1

    # Проверяем вызов VacancyRepository.get_or_create
    mock_vacancy_get_or_create.assert_called_once()
    args, kwargs = mock_vacancy_get_or_create.call_args
    assert kwargs['id_vacancy'] == '123'
    assert kwargs['title'] == 'Python-разработчик'
    assert kwargs['company'] == 'Acme Inc'
    assert kwargs['region'] == 'Moscow'

    # Проверяем вызов _fetch_full_vacancy_with_cache
    mock_fetch_full_vacancy.assert_called_once_with('123')

    # Проверяем нормализатор навыков
    assert mock_normalizer_get_skill.call_count == 2
    mock_normalizer_get_skill.assert_any_call('Python')
    mock_normalizer_get_skill.assert_any_call('Django')

    # Проверяем создание связей VacancySkill
    assert mock_vacancy_skill_create.call_count == 2
    mock_vacancy_skill_create.assert_any_call(vacancy=mock_vacancy, skill=mock_skill_python)
    mock_vacancy_skill_create.assert_any_call(vacancy=mock_vacancy, skill=mock_skill_django)

    # Проверяем, что описание сохранено
    mock_vacancy.save.assert_called_once_with(update_fields=['description'])

    # Кэш сохраняется
    mock_cache_save.assert_called_once()


# Тест обработки вакансии без навыков
@patch('concurrent.futures.ThreadPoolExecutor', lambda max_workers: SyncExecutor())
@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
@patch('core.services.cache_manager.VacancyCache.save')
@patch('core.services.cache_manager.VacancyCache.get')
@patch('core.services.vacancy_fetcher.datetime')
@patch('core.services.vacancy_fetcher.VacancySkillRepository.get_or_create')
@patch('core.services.skill_normalizer.SkillNormalizer.get_or_create_skill')
@patch('core.repository.VacancyRepository.get_or_create')
@patch('core.services.vacancy_fetcher.time.sleep')
@patch.object(HHVacancyFetcher, '_fetch_page')
@patch.object(HHVacancyFetcher, '_fetch_full_vacancy_with_cache')
@patch('core.models.Vacancy.objects.filter')
def test_fetch_and_save_handles_vacancy_without_skills(
    mock_vacancy_filter, mock_fetch_full_vacancy, mock_fetch_page, mock_sleep,
    mock_vacancy_get_or_create, mock_normalizer_get_skill,
    mock_vacancy_skill_create, mock_datetime, mock_cache_get, mock_cache_save,
    mock_cache_set, mock_cache_get_global, mock_cache_set_global
):
    mock_datetime.fromisoformat.return_value = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.UTC)
    mock_vacancy_filter.return_value.values_list.return_value = []  # нет существующих

    # Данные от API
    mock_fetch_page.return_value = {
        'items': [
            {
                'id': '456',
                'name': 'Manager',
                'published_at': '2025-01-01T10:00:00+03:00',
                'employer': {'name': 'Big Corp'},
                'area': None,
            }
        ],
        'pages': 1
    }

    # Полное описание – пустая строка
    mock_fetch_full_vacancy.return_value = {'description': ''}

    mock_vacancy = Mock(id_vacancy='456')
    mock_vacancy_get_or_create.return_value = (mock_vacancy, True)

    fetcher = HHVacancyFetcher(job_titles=['Manager'])
    saved_count = fetcher.fetch_and_save()
    assert saved_count == 1

    # Нормализатор и создание связей не вызывались
    mock_normalizer_get_skill.assert_not_called()
    mock_vacancy_skill_create.assert_not_called()
    # Описание не сохраняется, так как оно пустое
    mock_vacancy.save.assert_not_called()
    # Кэш сохраняется
    mock_cache_save.assert_called_once()
