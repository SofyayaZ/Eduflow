from django.urls import reverse
from django.utils import timezone

import pytest

from rest_framework import status
from core.models import Skill, UserSkill, UserTarget, GeneratedPath, PathStep, Vacancy, VacancySkill, SkillPrerequisite

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
        data = {'username': test_user.username, 'password': 'unique_password'}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

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

@pytest.mark.django_db
class TestJobTargetViewSet:
    def test_list_job_targets(self, auth_client, job_target):
        url = reverse('job-target-list')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['name'] == 'Python developer'

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

@pytest.mark.django_db
class TestGeneratePathView:
    def test_generate_path_missing_skills(self, auth_client, test_user, job_target, skill_python, skill_django):
        SkillPrerequisite.objects.create(skill=skill_django, prerequisite_skill=skill_python)
        # Создаём вакансию с регионом, совпадающим с регионом пользователя
        vacancy = Vacancy.objects.create(
            id_vacancy='v1',
            title='Python developer',
            company='C',
            source='hh',
            published_at=timezone.now(),
            region=test_user.preferred_region or 'Moscow'  # добавляем регион
        )
        VacancySkill.objects.create(vacancy=vacancy, skill=skill_python)
        VacancySkill.objects.create(vacancy=vacancy, skill=skill_django)
        # У пользователя есть Python, нет Django
        UserSkill.objects.create(user=test_user, skill=skill_python)
        target = UserTarget.objects.create(user=test_user, target_job=job_target)
        url = reverse('generate-path')
        response = auth_client.post(url, {'job_target_id': target.id})
        assert response.status_code == 200
        assert 'missing_skills' in response.data
        missing_names = [s['name'] for s in response.data['missing_skills']]
        assert 'Django' in missing_names
        # Проверяем, что путь создан
        path = GeneratedPath.objects.filter(user=test_user, target=target, is_current=True).first()
        assert path is not None
        steps = PathStep.objects.filter(generated_path=path)
        assert steps.count() >= 1
        assert steps.first().skill.name == 'Django'

    def test_no_vacancies(self, auth_client, test_user, job_target):
        # Убедимся, что у пользователя есть регион
        test_user.preferred_region = 'Moscow'
        test_user.save()
        target = UserTarget.objects.create(user=test_user, target_job=job_target)
        url = reverse('generate-path')
        response = auth_client.post(url, {'job_target_id': target.id})
        # Ожидаем 200, так как это не ошибка сервера, а информирование пользователя
        assert response.status_code == 200
        assert response.data['message'] == f'По вашему региону "{test_user.preferred_region}" вакансий для выбранной цели не найдено. Попробуйте сменить регион в профиле.'


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
