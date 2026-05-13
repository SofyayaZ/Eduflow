import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from core.models import (
    User,
    Skill,
    Vacancy,
    JobTarget,
    VacancySkill,
    SkillPrerequisite,
    UserSkill,
    UserTarget,
    GeneratedPath,
    PathStep,
)


@pytest.mark.django_db
class TestUserModel:
    def test_user_creation(self):
        user = User.objects.create_user(username="alice", password="pass")
        assert user.username == "alice"
        assert user.preferred_region == ""
        assert user.check_password("pass")
        assert user.is_active is True

    def test_user_str(self):
        user = User.objects.create_user(username="bob")
        assert str(user) == "bob"


@pytest.mark.django_db
class TestSkillModel:
    def test_skill_creation(self):
        skill = Skill.objects.create(name="Python", skill_type=Skill.SkillType.HARD)
        assert skill.name == "Python"
        assert skill.skill_type == Skill.SkillType.HARD

    def test_skill_default_type(self):
        skill = Skill.objects.create(name="Leadership")
        assert skill.skill_type == Skill.SkillType.HARD  # default

    def test_skill_str(self):
        skill = Skill.objects.create(name="Django", skill_type=Skill.SkillType.TOOL)
        assert str(skill) == "Django (Инструмент)"

    def test_unique_name(self):
        Skill.objects.create(name="Java")
        with pytest.raises(IntegrityError):
            Skill.objects.create(name="Java")

    def test_skill_type_choices(self):
        # допустимое значение
        skill = Skill.objects.create(name="Teamwork", skill_type="soft")
        assert skill.skill_type == "soft"
        
        # недопустимое – должно вызвать ValidationError при валидации
        skill_invalid = Skill(name="Bad", skill_type="invalid")
        with pytest.raises(ValidationError):
            skill_invalid.full_clean()


@pytest.mark.django_db
class TestVacancyModel:
    def test_vacancy_creation_minimal(self):
        vac = Vacancy.objects.create(
            id_vacancy="12345",
            title="Data Scientist",
            company="DataCorp",
            source="trudvsem",
        )
        assert vac.id_vacancy == "12345"
        assert vac.title == "Data Scientist"
        assert vac.company == "DataCorp"
        assert vac.source == "trudvsem"
        assert vac.fetched_at is not None
        assert vac.published_at is not None  # default=timezone.now
        assert vac.region == ""
        assert vac.description == ""
        assert vac.job_target is None

    def test_vacancy_with_job_target(self, job_target):  # job_target – фикстура
        vac = Vacancy.objects.create(
            id_vacancy="12346",
            title="Python Developer",
            company="Tech Inc",
            source="trudvsem",
            job_target=job_target,
        )
        assert vac.job_target == job_target

    def test_vacancy_str(self):
        vac = Vacancy.objects.create(
            id_vacancy="1", title="Backend Dev", company="Startup"
        )
        assert str(vac) == "Backend Dev (Startup)"

    def test_unique_id_vacancy(self):
        Vacancy.objects.create(id_vacancy="uniq1", title="A", company="C", source="S")
        with pytest.raises(IntegrityError):
            Vacancy.objects.create(id_vacancy="uniq1", title="B", company="C", source="S")

    def test_nullable_fields(self):
        # published_at может быть null? сейчас default=timezone.now, но если исправите на null=True – тест изменится
        vac = Vacancy.objects.create(
            id_vacancy="2", title="Dev", company="C", source="S"
        )
        assert vac.published_at is not None


@pytest.mark.django_db
class TestJobTargetModel:
    def test_job_target_creation(self):
        target = JobTarget.objects.create(name="Data Engineer", is_active=True)
        assert target.name == "Data Engineer"
        assert target.is_active is True

    def test_job_target_default_active(self):
        target = JobTarget.objects.create(name="ML Engineer")
        assert target.is_active is True

    def test_job_target_str(self):
        target = JobTarget.objects.create(name="DevOps")
        assert str(target) == "DevOps"

    def test_unique_name(self):
        JobTarget.objects.create(name="Analyst")
        with pytest.raises(IntegrityError):
            JobTarget.objects.create(name="Analyst")


@pytest.mark.django_db
class TestVacancySkillModel:
    def test_vacancy_skill_creation(self, vacancy, skill_python):
        vs = VacancySkill.objects.create(vacancy=vacancy, skill=skill_python)
        assert vs.vacancy == vacancy
        assert vs.skill == skill_python
        # Проверяем, что __str__ существует и возвращает что-то (невалидно)
        assert str(vs) is not None 
    
    def test_unique_vacancy_skill_pair(self, vacancy, skill_python):
        VacancySkill.objects.create(vacancy=vacancy, skill=skill_python)
        with pytest.raises(IntegrityError):
            VacancySkill.objects.create(vacancy=vacancy, skill=skill_python)

    def test_cascade_on_vacancy_delete(self, vacancy, skill_python):
        vs = VacancySkill.objects.create(vacancy=vacancy, skill=skill_python)
        vacancy.delete()
        assert VacancySkill.objects.filter(id=vs.id).count() == 0

    def test_cascade_on_skill_delete(self, vacancy, skill_python):
        vs = VacancySkill.objects.create(vacancy=vacancy, skill=skill_python)
        skill_python.delete()
        assert VacancySkill.objects.filter(id=vs.id).count() == 0


@pytest.mark.django_db
class TestSkillPrerequisiteModel:
    def test_skill_prerequisite_creation(self, skill_python, skill_django):
        prereq = SkillPrerequisite.objects.create(
            skill=skill_django, prerequisite_skill=skill_python
        )
        assert prereq.skill == skill_django
        assert prereq.prerequisite_skill == skill_python
        assert str(prereq) == f"{skill_python.name} → {skill_django.name}"

    def test_unique_constraint(self, skill_python, skill_django):
        SkillPrerequisite.objects.create(skill=skill_django, prerequisite_skill=skill_python)
        with pytest.raises(IntegrityError):
            SkillPrerequisite.objects.create(skill=skill_django, prerequisite_skill=skill_python)

    def test_no_self_prerequisite(self, skill_python):
        # Модель не запрещает, но бизнес-логика не должна такого допускать
        with pytest.raises(IntegrityError):
            # Если UniqueConstraint не запрещает, то создастся, но мы можем проверить и явно пропустить тест
            SkillPrerequisite.objects.create(skill=skill_python, prerequisite_skill=skill_python)

    def test_cascade_on_skill_delete(self, skill_python, skill_django):
        prereq = SkillPrerequisite.objects.create(skill=skill_django, prerequisite_skill=skill_python)
        skill_python.delete()
        assert SkillPrerequisite.objects.filter(id=prereq.id).count() == 0


@pytest.mark.django_db
class TestUserSkillModel:
    def test_user_skill_creation(self, test_user, skill_python):
        us = UserSkill.objects.create(user=test_user, skill=skill_python)
        assert us.user == test_user
        assert us.skill == skill_python

    def test_unique_together(self, test_user, skill_python):
        UserSkill.objects.create(user=test_user, skill=skill_python)
        with pytest.raises(IntegrityError):
            UserSkill.objects.create(user=test_user, skill=skill_python)

    def test_str(self, test_user, skill_python):
        us = UserSkill.objects.create(user=test_user, skill=skill_python)
        assert str(us) == f"{test_user.username} - {skill_python.name}"

    def test_cascade_on_user_delete(self, test_user, skill_python):
        us = UserSkill.objects.create(user=test_user, skill=skill_python)
        test_user.delete()
        assert UserSkill.objects.filter(id=us.id).count() == 0

    def test_cascade_on_skill_delete(self, test_user, skill_python):
        us = UserSkill.objects.create(user=test_user, skill=skill_python)
        skill_python.delete()
        assert UserSkill.objects.filter(id=us.id).count() == 0


@pytest.mark.django_db
class TestUserTargetModel:
    def test_user_target_creation(self, test_user, job_target):
        ut = UserTarget.objects.create(user=test_user, target_job=job_target)
        assert ut.user == test_user
        assert ut.target_job == job_target

    def test_unique_together(self, test_user, job_target):
        UserTarget.objects.create(user=test_user, target_job=job_target)
        with pytest.raises(IntegrityError):
            UserTarget.objects.create(user=test_user, target_job=job_target)

    def test_str(self, test_user, job_target):
        ut = UserTarget.objects.create(user=test_user, target_job=job_target)
        assert str(ut) == f"{test_user.username}: {job_target.name}"

    def test_cascade_on_user_delete(self, test_user, job_target):
        ut = UserTarget.objects.create(user=test_user, target_job=job_target)
        test_user.delete()
        assert UserTarget.objects.filter(id=ut.id).count() == 0

    def test_cascade_on_job_target_delete(self, test_user, job_target):
        ut = UserTarget.objects.create(user=test_user, target_job=job_target)
        job_target.delete()
        assert UserTarget.objects.filter(id=ut.id).count() == 0


@pytest.mark.django_db
class TestGeneratedPathModel:
    def test_generated_path_creation(self, test_user, user_target):
        path = GeneratedPath.objects.create(
            user=test_user,
            target=user_target,
            is_current=True
        )
        assert path.user == test_user
        assert path.target == user_target
        assert path.is_current is True
        assert path.generated_at is not None

    def test_is_current_default_false(self, test_user, user_target):
        path = GeneratedPath.objects.create(user=test_user, target=user_target)
        assert path.is_current is False

    def test_str(self, test_user, user_target, job_target):
        # job_target связан через user_target.target_job
        path = GeneratedPath.objects.create(user=test_user, target=user_target)
        expected = f"Path for {test_user.username} -> {user_target.target_job.name} ({path.generated_at})"
        assert str(path) == expected

    def test_cascade_on_user_delete(self, test_user, user_target):
        path = GeneratedPath.objects.create(user=test_user, target=user_target)
        test_user.delete()
        assert GeneratedPath.objects.filter(id=path.id).count() == 0

    def test_cascade_on_user_target_delete(self, test_user, user_target):
        path = GeneratedPath.objects.create(user=test_user, target=user_target)
        user_target.delete()
        assert GeneratedPath.objects.filter(id=path.id).count() == 0


@pytest.mark.django_db
class TestPathStepModel:
    def test_path_step_creation(self, generated_path, skill_python):
        step = PathStep.objects.create(
            generated_path=generated_path,
            skill=skill_python,
            step_order=1
        )
        assert step.generated_path == generated_path
        assert step.skill == skill_python
        assert step.step_order == 1

    def test_ordering(self, generated_path, skill_python, skill_django):
        step1 = PathStep.objects.create(generated_path=generated_path, skill=skill_django, step_order=2)
        step2 = PathStep.objects.create(generated_path=generated_path, skill=skill_python, step_order=1)
        steps = list(PathStep.objects.filter(generated_path=generated_path))
        assert steps[0] == step2  # step_order=1 first
        assert steps[1] == step1

    def test_str(self, generated_path, skill_python):
        step = PathStep.objects.create(generated_path=generated_path, skill=skill_python, step_order=3)
        assert str(step) == f"{generated_path}: step 3 - {skill_python.name}"

    def test_cascade_on_generated_path_delete(self, generated_path, skill_python):
        step = PathStep.objects.create(generated_path=generated_path, skill=skill_python, step_order=1)
        generated_path.delete()
        assert PathStep.objects.filter(id=step.id).count() == 0

    def test_cascade_on_skill_delete(self, generated_path, skill_python):
        step = PathStep.objects.create(generated_path=generated_path, skill=skill_python, step_order=1)
        skill_python.delete()
        assert PathStep.objects.filter(id=step.id).count() == 0

    # step_order уникальный в рамках одного пути
    def test_unique_step_order_per_path(self, generated_path, skill_python, skill_django):
        PathStep.objects.create(generated_path=generated_path, skill=skill_python, step_order=1)
        with pytest.raises(IntegrityError):
            PathStep.objects.create(generated_path=generated_path, skill=skill_django, step_order=1)
            