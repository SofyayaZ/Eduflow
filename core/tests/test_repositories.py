from datetime import timedelta
from django.utils import timezone
import pytest
from unittest.mock import patch   # ← правильный импорт
from core.models import GeneratedPath, Skill, UserSkill, UserTarget, Vacancy
from core.repository import (
    SkillRepository, VacancyRepository, 
    UserSkillRepository, GeneratedPathRepository
)

@pytest.mark.django_db
class TestSkillRepository:
    def test_get_or_create(self):
        skill, created = SkillRepository.get_or_create('Python')
        assert created is True
        assert skill.name == 'Python'

        skill2, created2 = SkillRepository.get_or_create('Python')
        assert created2 is False
        assert skill.id == skill2.id

    def test_bulk_create(self):
        names = ['Go', 'Rust', 'Go']
        created = SkillRepository.bulk_create(names)
        assert Skill.objects.count() == 2  # Go и Rust

    def test_delete(self):
        s = Skill.objects.create(name='Ruby')
        deleted, _ = SkillRepository.delete(s.id)
        assert deleted == 1
        assert not Skill.objects.filter(id=s.id).exists()

@pytest.mark.django_db
class TestVacancyRepository:
    def test_get_or_create(self, vacancy):
        vac_data = {
            'id_vacancy': '456',
            'title': 'Java Dev',
            'company': 'Company',
            'source': 'hh.ru',
            'published_at': timezone.now()   # добавлено
        }
        vac, created = VacancyRepository.get_or_create(**vac_data)
        assert created is True
        assert vac.title == 'Java Dev'

        vac2, created2 = VacancyRepository.get_or_create(**vac_data)
        assert created2 is False

    def test_delete_old_vacancies(self):
        now = timezone.now()
        old_time = now - timedelta(days=200)
        new_time = now

        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = old_time
            old_vacancy = Vacancy.objects.create(
                id_vacancy='old',
                title='Old',
                company='Old',
                source='hh',
                published_at=old_time
            )
            mock_now.return_value = new_time
            new_vacancy = Vacancy.objects.create(
                id_vacancy='new',
                title='New',
                company='New',
                source='hh',
                published_at=new_time
            )
            mock_now.return_value = now
            deleted = VacancyRepository.delete_old_vacancies()
        assert deleted == 1
        assert not Vacancy.objects.filter(id_vacancy='old').exists()
        assert Vacancy.objects.filter(id_vacancy='new').exists()

@pytest.mark.django_db
class TestUserSkillRepository:
    def test_add_and_remove(self, test_user, skill_python):   # user → test_user
        us, created = UserSkillRepository.add_skill(test_user, skill_python)
        assert created is True
        assert UserSkill.objects.filter(user=test_user, skill=skill_python).exists()

        deleted, _ = UserSkillRepository.remove_skill(test_user, skill_python)
        assert deleted == 1

    def test_bulk_add(self, test_user):   # user → test_user
        skills = [Skill.objects.create(name=f'Skill{i}') for i in range(3)]
        UserSkillRepository.bulk_add(test_user, skills)
        assert UserSkill.objects.filter(user=test_user).count() == 3

@pytest.mark.django_db
class TestGeneratedPathRepository:
    def test_create_with_limit(self, test_user, job_target):   # user → test_user
        target = UserTarget.objects.create(user=test_user, target_job=job_target)
        for i in range(11):
            GeneratedPathRepository.create_with_limit(test_user, target, is_current=(i == 10))
        assert GeneratedPath.objects.filter(user=test_user).count() == 10
        current = GeneratedPath.objects.filter(user=test_user, is_current=True).count()
        assert current == 1
        