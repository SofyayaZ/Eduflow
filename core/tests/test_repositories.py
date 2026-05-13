import pytest
from django.utils import timezone
from datetime import timedelta
from core.models import (
    Skill,
    Vacancy,
    VacancySkill,
    SkillPrerequisite,
    JobTarget,
    UserTarget,
    GeneratedPath,
    PathStep,
    UserSkill,
)
from core.repository import (
    SkillRepository,
    VacancyRepository,
    VacancySkillRepository,
    SkillPrerequisiteRepository,
    JobTargetRepository,
    UserTargetRepository,
    GeneratedPathRepository,
    PathStepRepository,
    UserSkillRepository,
)


# ================================ SkillRepository ================================

@pytest.mark.django_db
class TestSkillRepository:
    def test_get_all(self, skill_python, skill_django):
        skills = SkillRepository.get_all()
        assert skills.count() == 2
        assert skill_python in skills
        assert skill_django in skills

    def test_get_by_id(self, skill_python):
        skill = SkillRepository.get_by_id(skill_python.id)
        assert skill == skill_python

    def test_get_by_id_list(self, skill_python, skill_django):
        skills = SkillRepository.get_by_id_list([skill_python.id, skill_django.id])
        assert skills.count() == 2

    def test_get_by_name(self, skill_python):
        skill = SkillRepository.get_by_name("Python")
        assert skill == skill_python

    def test_get_skill_type_by_name(self, skill_python):
        skill_type = SkillRepository.get_skill_type_by_name("Python")
        assert skill_type == Skill.SkillType.HARD
        assert SkillRepository.get_skill_type_by_name("Unknown") is None

    def test_filter_by_skill_type(self, skill_python, skill_django):
        soft_skills = SkillRepository.filter_by_skill_type(Skill.SkillType.SOFT)
        assert soft_skills.count() == 0
        hard_skills = SkillRepository.filter_by_skill_type(Skill.SkillType.HARD)
        assert hard_skills.count() == 1
        assert hard_skills.first() == skill_python

    def test_create(self):
        skill = SkillRepository.create("Java", Skill.SkillType.HARD)
        assert skill.name == "Java"
        assert skill.skill_type == Skill.SkillType.HARD

    def test_get_or_create_existing(self, skill_python):
        skill, created = SkillRepository.get_or_create("Python", Skill.SkillType.TOOL)
        assert skill == skill_python
        assert created is False
        # Проверяем, что тип обновился, если отличается
        skill.refresh_from_db()
        assert skill.skill_type == Skill.SkillType.TOOL

    def test_get_or_create_new(self):
        skill, created = SkillRepository.get_or_create("Golang", Skill.SkillType.HARD)
        assert created is True
        assert skill.name == "Golang"
        assert skill.skill_type == Skill.SkillType.HARD

    def test_bulk_create(self):
        names = ["Rust", "C++", "Rust"]  # дубликат
        skills = SkillRepository.bulk_create(names, Skill.SkillType.HARD)
        assert len(skills) == 2  # bulk_create с ignore_conflicts=True вернёт 2 объекта
        assert Skill.objects.filter(name="Rust").exists()
        assert Skill.objects.filter(name="C++").exists()

    def test_update(self, skill_python):
        updated = SkillRepository.update(skill_python.id, name="Python3", skill_type=Skill.SkillType.TOOL)
        assert updated.name == "Python3"
        assert updated.skill_type == Skill.SkillType.TOOL
        skill_python.refresh_from_db()
        assert skill_python.name == "Python3"

    def test_delete(self, skill_python):
        SkillRepository.delete(skill_python.id)
        assert not Skill.objects.filter(id=skill_python.id).exists()

# ================================ VacancyRepository ================================

@pytest.mark.django_db
class TestVacancyRepository:
    def test_get_all(self, vacancy):
        vacancies = VacancyRepository.get_all()
        assert vacancies.count() == 1
        assert vacancy in vacancies

    def test_get_by_id(self, vacancy):
        vac = VacancyRepository.get_by_id(vacancy.id_vacancy)
        assert vac == vacancy

    def test_create(self, job_target):
        vac = VacancyRepository.create(
            id_vacancy="999",
            title="Test",
            company="TestCo",
            source="test",
            job_target=job_target
        )
        assert vac.id_vacancy == "999"
        assert vac.title == "Test"

    def test_get_or_create_new(self, job_target):
        vac, created = VacancyRepository.get_or_create(
            id_vacancy="888",
            title="New",
            company="NewCo",
            source="test",
            job_target=job_target
        )
        assert created is True
        assert vac.id_vacancy == "888"

    def test_get_or_create_existing(self, vacancy):
        vac, created = VacancyRepository.get_or_create(
            id_vacancy=vacancy.id_vacancy,
            title="UpdatedTitle",  # этот параметр не обновится, т.к. defaults не передаётся
            company=vacancy.company,
            source=vacancy.source,
        )
        assert created is False
        assert vac.title != "UpdatedTitle"  # не обновилось

    def test_bulk_create(self):
        data = [
            {"id_vacancy": "b1", "title": "Bulk1", "company": "C", "source": "test"},
            {"id_vacancy": "b2", "title": "Bulk2", "company": "C", "source": "test"},
        ]
        created = VacancyRepository.bulk_create(data)
        assert len(created) == 2

    def test_update(self, vacancy):
        updated = VacancyRepository.update(vacancy.id_vacancy, title="New Title", region="Moscow")
        assert updated.title == "New Title"
        assert updated.region == "Moscow"
        vacancy.refresh_from_db()
        assert vacancy.title == "New Title"

    def test_delete_old_vacancies(self, vacancy):
        # Создаём старую вакансию
        old_vac = Vacancy.objects.create(
            id_vacancy="old", title="old", company="weLoveTheCompany", source="testest",
            fetched_at=timezone.now() - timedelta(days=200)
        )
        deleted = VacancyRepository.delete_old_vacancies()
        assert deleted == 1
        assert Vacancy.objects.filter(id_vacancy="old").exists() is False
        assert Vacancy.objects.filter(id_vacancy=vacancy.id_vacancy).exists() is True

    def test_get_existing_ids(self, vacancy):
        ids = VacancyRepository.get_existing_ids(["123", "nonexistent"])
        assert ids == {"123"}

# ================================ VacancySkillRepository ================================

@pytest.mark.django_db
class TestVacancySkillRepository:
    def test_get_or_create(self, vacancy, skill_python):
        vs, created = VacancySkillRepository.get_or_create(vacancy, skill_python)
        assert created is True
        assert vs.vacancy == vacancy
        assert vs.skill == skill_python

    def test_bulk_create(self, vacancy, skill_python, skill_django):
        relations = [
            {"vacancy": vacancy, "skill": skill_python},
            {"vacancy": vacancy, "skill": skill_django},
        ]
        created = VacancySkillRepository.bulk_create(relations)
        assert len(created) == 2
        assert VacancySkill.objects.filter(vacancy=vacancy).count() == 2

    def test_get_skills_for_vacancy(self, vacancy, skill_python, skill_django):
        VacancySkill.objects.create(vacancy=vacancy, skill=skill_python)
        VacancySkill.objects.create(vacancy=vacancy, skill=skill_django)
        skills = VacancySkillRepository.get_skills_for_vacancy(vacancy.id_vacancy)
        assert skills.count() == 2
        assert skill_python in [vs.skill for vs in skills]

    def test_get_skill_importance_for_job_title(self, vacancy, skill_python, skill_django, job_target):
        # Создаём вакансию с заголовком, содержащим job_title
        vac2 = Vacancy.objects.create(
            id_vacancy="456",
            title="Backend Developer",
            company="C",
            source="test",
            job_target=job_target
        )
        VacancySkill.objects.create(vacancy=vacancy, skill=skill_python)
        VacancySkill.objects.create(vacancy=vacancy, skill=skill_django)
        # Вторая вакансия с skill_python
        VacancySkill.objects.create(vacancy=vac2, skill=skill_python)

        importance = VacancySkillRepository.get_skill_importance_for_job_title("Backend Developer")
        # importance – список словарей [{'skill': id, 'importance': count}]
        assert len(importance) == 2
        imp_dict = {item['skill']: item['importance'] for item in importance}
        assert imp_dict[skill_python.id] == 2
        assert imp_dict[skill_django.id] == 1

# ================================ SkillPrerequisiteRepository ================================

@pytest.mark.django_db
class TestSkillPrerequisiteRepository:
    def test_get_or_create(self, skill_python, skill_django):
        prereq, created = SkillPrerequisiteRepository.get_or_create(skill_django, skill_python)
        assert created is True
        assert prereq.skill == skill_django
        assert prereq.prerequisite_skill == skill_python

    def test_bulk_create(self, skill_python, skill_django):
        prereqs = [
            {"skill": skill_django, "prerequisite_skill": skill_python},
        ]
        created = SkillPrerequisiteRepository.bulk_create(prereqs)
        assert len(created) == 1
        assert SkillPrerequisite.objects.filter(skill=skill_django).exists()

    def test_get_prerequisites(self, skill_python, skill_django):
        SkillPrerequisite.objects.create(skill=skill_django, prerequisite_skill=skill_python)
        prereqs = SkillPrerequisiteRepository.get_prerequisites(skill_django)
        assert prereqs.count() == 1
        assert prereqs[0].prerequisite_skill == skill_python

    def test_exists(self, skill_python, skill_django):
        assert SkillPrerequisiteRepository.exists(skill_python, skill_django) is False
        SkillPrerequisite.objects.create(skill=skill_django, prerequisite_skill=skill_python)
        assert SkillPrerequisiteRepository.exists(skill_python, skill_django) is True

# ================================ JobTargetRepository ================================

@pytest.mark.django_db
class TestJobTargetRepository:
    def test_get_or_create_new(self):
        target, created = JobTargetRepository.get_or_create("Data Scientist")
        assert created is True
        assert target.name == "Data Scientist"

    def test_get_or_create_existing(self, job_target):
        target, created = JobTargetRepository.get_or_create(job_target.name)
        assert created is False
        assert target == job_target

    def test_get_by_name(self, job_target):
        target = JobTargetRepository.get_by_name(job_target.name)
        assert target == job_target
        assert JobTargetRepository.get_by_name("No") is None

    def test_get_by_id(self, job_target):
        target = JobTargetRepository.get_by_id(job_target.id)
        assert target == job_target

    def test_get_active(self, job_target):
        active = JobTargetRepository.get_active()
        assert job_target in active
        # Создаём неактивный
        inactive = JobTarget.objects.create(name="Inactive", is_active=False)
        active = JobTargetRepository.get_active()
        assert inactive not in active

    def test_delete(self, job_target):
        JobTargetRepository.delete(job_target.id)
        assert not JobTarget.objects.filter(id=job_target.id).exists()

# ================================ UserTargetRepository ================================

@pytest.mark.django_db
class TestUserTargetRepository:
    def test_get_for_user(self, test_user, user_target):
        targets = UserTargetRepository.get_for_user(test_user)
        assert targets.count() == 1
        assert targets[0] == user_target

    def test_create(self, test_user, job_target):
        ut = UserTargetRepository.create(test_user, job_target)
        assert ut.user == test_user
        assert ut.target_job == job_target

    def test_delete(self, user_target):
        UserTargetRepository.delete(user_target.id)
        assert not UserTarget.objects.filter(id=user_target.id).exists()

    def test_get_active_targets(self, test_user, job_target):
        # алиас для get_for_user
        targets = UserTargetRepository.get_active_targets(test_user)
        assert targets.count() == 0  # ещё не создано
        UserTarget.objects.create(user=test_user, target_job=job_target)
        targets = UserTargetRepository.get_active_targets(test_user)
        assert targets.count() == 1

# ================================ GeneratedPathRepository ================================

@pytest.mark.django_db
class TestGeneratedPathRepository:
    def test_create_with_limit_within_limit(self, test_user, user_target):
        # Создаём до 10 путей
        for i in range(5):
            path = GeneratedPathRepository.create_with_limit(test_user, user_target, is_current=(i==0))
        assert GeneratedPath.objects.filter(user=test_user).count() == 5

    def test_create_with_limit_exceeds_limit(self, test_user, user_target):
        # Создаём 10 путей
        for i in range(10):
            GeneratedPathRepository.create_with_limit(test_user, user_target, is_current=False)
        # Одиннадцатый – должен удалить самый старый (не текущий)
        GeneratedPathRepository.create_with_limit(test_user, user_target, is_current=False)
        assert GeneratedPath.objects.filter(user=test_user).count() == 10

    def test_create_with_limit_current(self, test_user, user_target):
        path = GeneratedPathRepository.create_with_limit(test_user, user_target, is_current=True)
        assert path.is_current is True
        # Проверяем, что предыдущие текущие для этой пары сброшены
        another = GeneratedPathRepository.create_with_limit(test_user, user_target, is_current=True)
        path.refresh_from_db()
        assert path.is_current is False
        assert another.is_current is True

    def test_get_current_for_target(self, test_user, user_target):
        assert GeneratedPathRepository.get_current_for_target(test_user, user_target) is None
        path = GeneratedPathRepository.create_with_limit(test_user, user_target, is_current=True)
        current = GeneratedPathRepository.get_current_for_target(test_user, user_target)
        assert current == path

    def test_get_history_for_user(self, test_user, user_target):
        path1 = GeneratedPathRepository.create_with_limit(test_user, user_target, is_current=False)
        path2 = GeneratedPathRepository.create_with_limit(test_user, user_target, is_current=True)
        history = GeneratedPathRepository.get_history_for_user(test_user)
        assert list(history) == [path2, path1]  # order by -generated_at

# ================================ PathStepRepository ================================

@pytest.mark.django_db
class TestPathStepRepository:
    def test_create(self, generated_path, skill_python):
        step = PathStepRepository.create(generated_path, skill_python, 1)
        assert step.generated_path == generated_path
        assert step.skill == skill_python
        assert step.step_order == 1

    def test_bulk_create(self, generated_path, skill_python, skill_django):
        steps_data = [
            {"generated_path": generated_path, "skill": skill_python, "step_order": 1},
            {"generated_path": generated_path, "skill": skill_django, "step_order": 2},
        ]
        created = PathStepRepository.bulk_create(steps_data)
        assert len(created) == 2
        assert PathStep.objects.filter(generated_path=generated_path).count() == 2

    def test_get_for_path(self, generated_path, skill_python, skill_django):
        step1 = PathStep.objects.create(generated_path=generated_path, skill=skill_python, step_order=2)
        step2 = PathStep.objects.create(generated_path=generated_path, skill=skill_django, step_order=1)
        steps = PathStepRepository.get_for_path(generated_path)
        assert list(steps) == [step2, step1]  # ordering by step_order

# ================================ UserSkillRepository ================================

@pytest.mark.django_db
class TestUserSkillRepository:
    def test_get_skills_for_user(self, test_user, skill_python, skill_django):
        UserSkill.objects.create(user=test_user, skill=skill_python)
        UserSkill.objects.create(user=test_user, skill=skill_django)
        skills = UserSkillRepository.get_skills_for_user(test_user)
        assert skills.count() == 2
        assert skill_python in [us.skill for us in skills]

    def test_add_skill(self, test_user, skill_python):
        us, created = UserSkillRepository.add_skill(test_user, skill_python)
        assert created is True
        assert us.user == test_user
        assert us.skill == skill_python
        # Добавление повторное
        us2, created2 = UserSkillRepository.add_skill(test_user, skill_python)
        assert created2 is False
        assert us2 == us

    def test_remove_skill(self, test_user, skill_python):
        UserSkill.objects.create(user=test_user, skill=skill_python)
        deleted = UserSkillRepository.remove_skill(test_user, skill_python)
        assert deleted[0] == 1  # количество удалённых
        assert not UserSkill.objects.filter(user=test_user, skill=skill_python).exists()

    def test_bulk_add(self, test_user, skill_python, skill_django):
        skills = [skill_python, skill_django]
        created = UserSkillRepository.bulk_add(test_user, skills)
        assert len(created) == 2
        assert UserSkill.objects.filter(user=test_user).count() == 2
