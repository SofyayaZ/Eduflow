import pytest
from core.models import Skill, UserSkill, Vacancy, VacancySkill
from core.services.skill_matching import SkillMatchingService
from datetime import datetime


@pytest.fixture
def skills(db):
    skill1 = Skill.objects.create(name='CI/CD')
    skill2 = Skill.objects.create(name='kubernetes')
    skill3 = Skill.objects.create(name='harbor')
    return {'CI/CD': skill1, 'kubernetes': skill2, 'harbor': skill3}

@pytest.fixture
def vacancies_and_skills(db, skills):
    vacancy1 = Vacancy.objects.create(
        id_vacancy='1', title='DevOps engineer', company='Catchan', source='hh',
        published_at=datetime.strptime('2026-02-01 13:13:13', '%Y-%m-%d %H:%M:%S')
    )
    VacancySkill.objects.create(vacancy=vacancy1, skill=skills['CI/CD'])
    VacancySkill.objects.create(vacancy=vacancy1, skill=skills['kubernetes'])
    vacancy2 = Vacancy.objects.create(
        id_vacancy='2', title='DevOps engineer', company='Meowmeow', source='hh',
        published_at=datetime.strptime('2026-03-04 11:19:17', '%Y-%m-%d %H:%M:%S')
    )
    VacancySkill.objects.create(vacancy=vacancy2, skill=skills['CI/CD'])
    VacancySkill.objects.create(vacancy=vacancy2, skill=skills['kubernetes'])
    VacancySkill.objects.create(vacancy=vacancy2, skill=skills['harbor'])
    # Возвращаем что-то, но не обязательно
    return None

def test_get_required_skills_for_target(vacancies_and_skills, skills):
    required_skills = SkillMatchingService.get_required_skills_for_target(target_job_title='DevOps engineer')
    assert len(required_skills) == 3
    assert required_skills[0][0].name == 'CI/CD'
    assert required_skills[0][1] == 2
    assert required_skills[1][0].name == 'kubernetes'
    assert required_skills[1][1] == 2
    assert required_skills[2][0].name == 'harbor'
    assert required_skills[2][1] == 1

def test_get_missing_skills(test_user, vacancies_and_skills, skills):
    UserSkill.objects.create(user=test_user, skill=skills['kubernetes'])
    UserSkill.objects.create(user=test_user, skill=skills['harbor'])
    missing_skills = SkillMatchingService.get_missing_skills(test_user, target_job_title='DevOps engineer')
    assert len(missing_skills) == 1
    assert missing_skills[0][0].name == 'CI/CD'
    assert missing_skills[0][1] == 2