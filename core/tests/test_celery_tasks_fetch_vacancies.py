# import pytest
# from core.tasks import fetch_vacancies_from_hh
# from unittest.mock import patch, Mock

# @pytest.mark.django_db
# class TestFetchVacanciesTask:
#     @patch('core.services.vacancy_fetcher.HHVacancyFetcher')  # ← правильный путь
#     def test_task_success(self, mock_fetcher_class, job_target):
#         mock_fetcher = Mock()
#         mock_fetcher.fetch_and_save.return_value = 10
#         mock_fetcher_class.return_value = mock_fetcher

#         result = fetch_vacancies_from_hh()
#         mock_fetcher_class.assert_called_once_with(
#             job_titles=[job_target.name],
#             region_code=None
#         )
#         mock_fetcher.fetch_and_save.assert_called_once()
#         assert result == 10

#     @patch('core.services.vacancy_fetcher.HHVacancyFetcher')
#     def test_task_retry_on_exception(self, mock_fetcher_class, job_target):
#         mock_fetcher = Mock()
#         mock_fetcher.fetch_and_save.side_effect = Exception('API error')
#         mock_fetcher_class.return_value = mock_fetcher

#         with patch('celery.app.task.Task.retry') as mock_retry:
#             mock_retry.side_effect = Exception('Retry called')  # чтобы остановить ретрай
#             try:
#                 fetch_vacancies_from_hh()
#             except Exception:
#                 pass
#             mock_retry.assert_called_once_with(
#                 exc=mock_fetcher.fetch_and_save.side_effect,
#                 countdown=60
#             )

#     @patch('core.services.vacancy_fetcher.HHVacancyFetcher')
#     def test_fetch_task_eager(self, mock_fetcher_class, job_target, settings):
#         settings.CELERY_TASK_ALWAYS_EAGER = True
#         mock_fetcher = Mock()
#         mock_fetcher.fetch_and_save.return_value = 7
#         mock_fetcher_class.return_value = mock_fetcher

#         result = fetch_vacancies_from_hh()
#         assert result == 7