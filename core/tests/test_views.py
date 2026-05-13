import pytest
from django.urls import reverse
from rest_framework import status
from core.models import Skill, User, UserTarget, GeneratedPath, PathStep
from unittest.mock import Mock, patch

# -------------------- AuthEndpoints --------------------
@pytest.mark.django_db
class TestAuthEndpoints:
    def test_register(self, api_client):
        url = reverse('register')
        data = {'username': 'newuser', 'password': 'pass123', 'email': 'new@example.com'}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data

    def test_token_obtain(self, api_client, test_user):
        url = reverse('token_obtain_pair')
        data = {'username': test_user.username, 'password': 'testpass'}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

# -------------------- ProfileView --------------------
@pytest.mark.django_db
class TestProfileView:
    def test_get_profile(self, auth_client, test_user):
        url = reverse('profile')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.data['username'] == test_user.username

    def test_update_profile(self, auth_client, test_user):
        url = reverse('profile')
        response = auth_client.patch(url, {'preferred_region': 'SPB'})
        assert response.status_code == 200
        test_user.refresh_from_db()
        assert test_user.preferred_region == 'SPB'

# -------------------- JobTargetViewSet --------------------
@pytest.mark.django_db
class TestJobTargetViewSet:
    def test_list_job_targets(self, auth_client, job_target):
        url = reverse('job-target-list')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['name'] == 'Backend Developer'

# -------------------- UserTargetViewSet --------------------
@pytest.mark.django_db
class TestUserTargetViewSet:
    def test_create_user_target(self, auth_client, test_user, job_target):
        url = reverse('user-target-list')
        data = {'target_job_id': job_target.id}
        response = auth_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert UserTarget.objects.filter(user=test_user, target_job=job_target).exists()

    def test_list_user_targets(self, auth_client, test_user, job_target):
        UserTarget.objects.create(user=test_user, target_job=job_target)
        url = reverse('user-target-list')
        response = auth_client.get(url)
        assert len(response.data) == 1
        assert response.data[0]['target_job']['name'] == job_target.name

# -------------------- GeneratePathView --------------------
@pytest.mark.django_db
class TestGeneratePathView:
    def test_missing_job_target_id(self, auth_client):
        url = reverse('generate-path')
        response = auth_client.post(url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'job_target_id' in response.data['error']

    def test_invalid_target_id(self, auth_client, test_user, job_target):
        # Создаём другого пользователя (импорт User уже есть)
        other_user = User.objects.create_user(username="other", password="pass")
        other_target = UserTarget.objects.create(user=other_user, target_job=job_target)
        url = reverse('generate-path')
        response = auth_client.post(url, {'job_target_id': other_target.id})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error'] == 'User target not found'

    # Исправляем пути в декораторах
    @patch('core.services.skill_matching.SkillMatchingService.has_vacancies_for_target')
    def test_no_vacancies(self, mock_has_vacancies, auth_client, user_target):
        mock_has_vacancies.return_value = False
        url = reverse('generate-path')
        response = auth_client.post(url, {'job_target_id': user_target.id})
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        assert 'вакансий' in response.data['message'].lower()

    @patch('core.services.skill_matching.SkillMatchingService.get_missing_skills')
    @patch('core.services.skill_matching.SkillMatchingService.has_vacancies_for_target')
    def test_no_missing_skills(self, mock_has_vacancies, mock_get_missing, auth_client, user_target):
        mock_has_vacancies.return_value = True
        mock_get_missing.return_value = []
        url = reverse('generate-path')
        response = auth_client.post(url, {'job_target_id': user_target.id})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Отсутствующих навыков не найдено'

    @patch('core.services.path_builder.PathBuilder._expand_missing_with_prerequisites')
    @patch('core.services.path_builder.PathBuilder.build_sequence')
    @patch('core.services.path_builder.PathBuilder.create_path')
    @patch('core.services.skill_matching.SkillMatchingService.get_missing_skills')
    @patch('core.services.skill_matching.SkillMatchingService.has_vacancies_for_target')
    @patch('core.repository.UserSkillRepository.get_skills_for_user')
    def test_successful_path_creation(
        self, mock_user_skills, mock_has_vacancies, mock_get_missing,
        mock_create_path, mock_build_sequence, mock_expand,
        auth_client, user_target, test_user, skill_python, skill_django
    ):
        # Устанавливаем регион пользователя
        test_user.preferred_region = 'Moscow'
        test_user.save()

        mock_has_vacancies.return_value = True
        mock_get_missing.return_value = [(skill_django, 5)]
        mock_user_skills.return_value.values_list.return_value = [skill_python.id]

        expanded = [skill_django, skill_python]
        mock_expand.return_value = expanded
        sequence = [skill_python, skill_django]
        mock_build_sequence.return_value = sequence
        mock_path = Mock(spec=GeneratedPath)
        mock_path.id = 42
        mock_create_path.return_value = mock_path

        url = reverse('generate-path')
        response = auth_client.post(url, {'job_target_id': user_target.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data['path_id'] == 42
        assert len(data['ordered_steps']) == 2
        assert data['ordered_steps'][0]['name'] == 'Python'
        assert data['ordered_steps'][1]['name'] == 'Django'
        assert {s['name'] for s in data['missing_skills']} == {'Python', 'Django'}
        assert data['soft_skills'] == []
        assert 'graph' in data

        mock_has_vacancies.assert_called_once_with(user_target.target_job, region='Moscow')
        mock_get_missing.assert_called_once_with(test_user, user_target.target_job.name)
        mock_user_skills.assert_called_once_with(test_user)
        mock_expand.assert_called_once_with([skill_django], {skill_python.id})
        mock_build_sequence.assert_called_once_with(expanded, {skill_python.id})
        mock_create_path.assert_called_once_with(test_user, user_target, sequence[:10])

    @patch('core.services.path_builder.PathBuilder.build_sequence')
    @patch('core.services.skill_matching.SkillMatchingService.get_missing_skills')
    @patch('core.services.skill_matching.SkillMatchingService.has_vacancies_for_target')
    def test_build_sequence_error(
        self, mock_has_vacancies, mock_get_missing, mock_build_sequence,
        auth_client, user_target, skill_python, skill_django
    ):
        mock_has_vacancies.return_value = True
        mock_get_missing.return_value = [(skill_django, 5)]
        mock_build_sequence.side_effect = ValueError("Cycle detected")

        url = reverse('generate-path')
        response = auth_client.post(url, {'job_target_id': user_target.id})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'Cycle detected' in response.data['error']

    @patch('core.services.path_builder.PathBuilder.create_path')
    @patch('core.services.path_builder.PathBuilder.build_sequence')
    @patch('core.services.path_builder.PathBuilder._expand_missing_with_prerequisites')
    @patch('core.services.skill_matching.SkillMatchingService.get_missing_skills')
    @patch('core.services.skill_matching.SkillMatchingService.has_vacancies_for_target')
    def test_create_path_exception(
        self, mock_has_vacancies, mock_get_missing, mock_expand,
        mock_build_sequence, mock_create_path,
        auth_client, user_target, skill_python, skill_django
    ):
        mock_has_vacancies.return_value = True
        mock_get_missing.return_value = [(skill_django, 5)]
        mock_expand.return_value = [skill_django, skill_python]
        mock_build_sequence.return_value = [skill_python, skill_django]
        mock_create_path.side_effect = Exception("DB error")

        url = reverse('generate-path')
        response = auth_client.post(url, {'job_target_id': user_target.id})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['error'] == 'Не удалось сохранить траекторию'

    def test_truncation_to_10_steps(self, auth_client, user_target, test_user):
        skills = [Skill.objects.create(name=f"Skill{i}", skill_type=Skill.SkillType.HARD) for i in range(15)]
        with patch('core.services.skill_matching.SkillMatchingService.has_vacancies_for_target', return_value=True), \
             patch('core.services.skill_matching.SkillMatchingService.get_missing_skills') as mock_missing, \
             patch('core.repository.UserSkillRepository.get_skills_for_user') as mock_user_skills, \
             patch('core.services.path_builder.PathBuilder._expand_missing_with_prerequisites') as mock_expand, \
             patch('core.services.path_builder.PathBuilder.build_sequence') as mock_sequence, \
             patch('core.services.path_builder.PathBuilder.create_path') as mock_create_path:

            mock_missing.return_value = [(s, 1) for s in skills]
            mock_user_skills.return_value.values_list.return_value = []
            mock_expand.return_value = skills
            mock_sequence.return_value = skills
            mock_create_path.return_value = Mock(id=1)

            url = reverse('generate-path')
            response = auth_client.post(url, {'job_target_id': user_target.id})
            assert response.status_code == 200
            assert len(response.data['ordered_steps']) == 10

# -------------------- PathHistoryView --------------------
@pytest.mark.django_db
class TestPathHistoryView:
    def test_history(self, auth_client, test_user, job_target):
        target = UserTarget.objects.create(user=test_user, target_job=job_target)
        path = GeneratedPath.objects.create(user=test_user, target=target, is_current=True)
        skill = Skill.objects.create(name='Docker')
        PathStep.objects.create(generated_path=path, skill=skill, step_order=1)
        url = reverse('path-history')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['target']['target_job']['name'] == job_target.name
        assert response.data[0]['steps'][0]['skill'] == 'Docker'
