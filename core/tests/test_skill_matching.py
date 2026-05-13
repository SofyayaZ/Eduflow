import pytest
from core.models import Skill, UserSkill, Vacancy, VacancySkill
from core.services.skill_matching import SkillMatchingService
from datetime import datetime
from django.utils import timezone


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
    required_skills = SkillMatchingService.get_required_skills_for_target(job_target_title='DevOps engineer')
    assert len(required_skills) == 3
    assert required_skills[0][0].name == 'CI/CD'
    assert required_skills[0][1] == 2
    assert required_skills[1][0].name == 'kubernetes'
    assert required_skills[1][1] == 2
    assert required_skills[2][0].name == 'harbor'
    assert required_skills[2][1] == 1

def test_get_missing_skills(test_user, skills):
    from core.models import Vacancy, VacancySkill
    
    # Создаём вакансию для DevOps engineer
    vacancy = Vacancy.objects.create(
        id_vacancy='devops_vacancy_1',
        title='DevOps engineer',
        company='TestCompany',
        source='test',
        published_at=timezone.now(),
        region='Moscow'
    )
    # Создаём связи вакансии с навыками (с указанием важности через количество вакансий)
    # Для простоты создадим три связи: CI/CD, kubernetes, harbor
    # Чтобы получить importance = 2 для CI/CD, нужно создать две вакансии с этим навыком
    VacancySkill.objects.create(vacancy=vacancy, skill=skills['CI/CD'])
    # Вторая вакансия для увеличения importance CI/CD
    vacancy2 = Vacancy.objects.create(
        id_vacancy='devops_vacancy_2',
        title='DevOps engineer',
        company='TestCompany',
        source='test',
        published_at=timezone.now(),
        region='Moscow'
    )
    VacancySkill.objects.create(vacancy=vacancy2, skill=skills['CI/CD'])
    
    # Для kubernetes и harbor – по одной вакансии
    VacancySkill.objects.create(vacancy=vacancy, skill=skills['kubernetes'])
    VacancySkill.objects.create(vacancy=vacancy, skill=skills['harbor'])
    
    # У пользователя уже есть kubernetes и harbor
    UserSkill.objects.create(user=test_user, skill=skills['kubernetes'])
    UserSkill.objects.create(user=test_user, skill=skills['harbor'])
    
    missing_skills = SkillMatchingService.get_missing_skills(test_user, job_target_title='DevOps engineer')
    assert len(missing_skills) == 1
    assert missing_skills[0][0].name == 'CI/CD'
    assert missing_skills[0][1] == 2   # importance = количество вакансий с этим навыком = 2
