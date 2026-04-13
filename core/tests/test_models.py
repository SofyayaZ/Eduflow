import pytest
from django.db import IntegrityError
from core.models import User, Skill, Vacancy, UserSkill, JobTarget, UserTarget, GeneratedPath, PathStep, SkillPrerequisite

@pytest.mark.django_db
class TestUserModel:
    def test_user_creation(self):
        user = User.objects.create_user(username='john', password='pass')
        assert user.username == 'john'
        assert user.preferred_region == ''

    def test_user_str(self, test_user):
        assert str(test_user) == test_user.username

@pytest.mark.django_db
class TestSkillModel:
    def test_skill_str(self, skill_python):
        assert str(skill_python) == 'Python'

    def test_skill_unique_name(self):
        Skill.objects.create(name='Java')
        with pytest.raises(IntegrityError):
            Skill.objects.create(name='Java')

@pytest.mark.django_db
class TestVacancyModel:
    def test_vacancy_str(self, vacancy):
        assert str(vacancy) == 'Python Developer (Test Company)'

@pytest.mark.django_db
class TestUserSkillModel:
    def test_unique_together(self,test_user, skill_python):
        UserSkill.objects.create(user=test_user, skill=skill_python)
        with pytest.raises(IntegrityError):
            UserSkill.objects.create(user=test_user, skill=skill_python)

@pytest.mark.django_db
class TestSkillPrerequisiteModel:
    def test_unique_constraint(self, skill_python, skill_django):
        SkillPrerequisite.objects.create(skill=skill_django, prerequisite_skill=skill_python)
        with pytest.raises(IntegrityError):
            SkillPrerequisite.objects.create(skill=skill_django, prerequisite_skill=skill_python)
