# import pytest

# from core.tasks import delete_old_vacancies
# from unittest.mock import patch


# @pytest.mark.django_db
# class TestDeleteOldVacanciesTask:
#     @patch('core.repository.VacancyRepository.delete_old_vacancies')
#     def test_task_calls_repository(self, mock_delete):
#         mock_delete.return_value = 5
#         result = delete_old_vacancies()
#         mock_delete.assert_called_once()
#         assert result == 5
        