from django.utils import timezone

import pytest
import uuid
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from core.models import JobTarget, Skill, UserTarget, Vacancy
from core.services.vacancy_fetcher import HHVacancyFetcher
from dotenv import load_dotenv


load_dotenv()

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def auth_client(api_client, test_user):
    api_client.force_authenticate(user=test_user)
    return api_client

@pytest.fixture
def test_user(db):
    unique_username = f'testuser_{uuid.uuid4()}'
    user = User.objects.create_user(
        username=unique_username,
        password='unique_password',
        preferred_region='Moscow'
    )
    return user


@pytest.fixture
def hh_fetcher():
    return HHVacancyFetcher(job_titles=['Python developer'], region_code=1)

@pytest.fixture
def job_target(db):
    return JobTarget.objects.create(name='Python developer', is_active=True)

@pytest.fixture
def user_target(db, test_user, job_target):
    return UserTarget.objects.create(user=test_user, target_job=job_target)

@pytest.fixture
def skills(db):
    python = Skill.objects.create(name='Python')
    django = Skill.objects.create(name='Django')
    sql = Skill.objects.create(name='SQL')
    java = Skill.objects.create(name='Java')
    return {'python': python, 'django': django, 'sql': sql, 'java': java}

# Если нужен отдельный skill_python, skill_django – можно определить их отдельно
@pytest.fixture
def skill_python(db):
    return Skill.objects.create(name='Python')

@pytest.fixture
def skill_django(db):
    return Skill.objects.create(name='Django')

@pytest.fixture
def skill_pandas(db):
    return Skill.objects.create(name='Pandas')

@pytest.fixture
def vacancy(db):
    return Vacancy.objects.create(
        id_vacancy='123',
        title='Python Developer',
        company='Test Company',
        source='hh.ru',
        region='Moscow',
        published_at=timezone.now()
    )
