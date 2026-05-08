import pytest
from core.models import User, Skill, Vacancy, JobTarget, UserTarget, GeneratedPath
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def auth_client(test_user):
    client = APIClient()
    refresh = RefreshToken.for_user(test_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="testuser", password="testpass")

@pytest.fixture
def skill_python(db):
    return Skill.objects.create(name="Python", skill_type=Skill.SkillType.HARD)

@pytest.fixture
def skill_django(db):
    return Skill.objects.create(name="Django", skill_type=Skill.SkillType.TOOL)

@pytest.fixture
def skill_postgresql(db):
    return Skill.objects.create(name="PostgreSQL", skill_type=Skill.SkillType.TOOL)

@pytest.fixture
def job_target(db):
    return JobTarget.objects.create(name="Backend Developer", is_active=True)

@pytest.fixture
def vacancy(db, job_target):
    return Vacancy.objects.create(
        id_vacancy="123",
        title="Backend Dev",
        company="Tech",
        source="trudvsem",
        job_target=job_target,
    )

@pytest.fixture
def user_target(db, test_user, job_target):
    return UserTarget.objects.create(user=test_user, target_job=job_target)

@pytest.fixture
def generated_path(db, test_user, user_target):
    return GeneratedPath.objects.create(user=test_user, target=user_target, is_current=False)
