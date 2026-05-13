from typing import List

from django.utils import timezone
from datetime import timedelta
from .models import (
    JobTarget, Skill, Vacancy, VacancySkill, SkillPrerequisite,
    UserTarget, GeneratedPath, PathStep, UserSkill
)
from django.db.models import Count
from django.contrib.postgres.search import SearchVector, SearchQuery


class SkillRepository:
    @staticmethod
    def get_all():
        return Skill.objects.all()
    
    @staticmethod
    def get_by_id(skill_id):
        return Skill.objects.get(id=skill_id)
    
    @staticmethod
    def get_by_id_list(ids):
        return Skill.objects.filter(id__in=ids)
    
    @staticmethod
    def get_by_name(name):
        return Skill.objects.filter(name=name).first()
    
    @staticmethod
    def get_skill_type_by_name(name):
        skill = Skill.objects.only('skill_type').filter(name=name).first()
        return skill.skill_type if skill else None
    
    @staticmethod
    def filter_by_skill_type(skill_type):
        return Skill.objects.filter(skill_type=skill_type)
    
    @staticmethod
    def create(name, skill_type=Skill.SkillType.HARD):
        return Skill.objects.create(name=name, skill_type=skill_type)
    
    @staticmethod
    def get_or_create(name, skill_type=Skill.SkillType.HARD):
        skill, created = Skill.objects.get_or_create(
            name=name,
            defaults={'skill_type': skill_type}
        )
        if not created and skill.skill_type != skill_type:
            skill.skill_type = skill_type
            skill.save(update_fields=['skill_type'])
        return skill, created
    
    @staticmethod
    def bulk_create(names, skill_type=Skill.SkillType.HARD):
        skills = [Skill(name=name, skill_type=skill_type) for name in set(names)]
        return Skill.objects.bulk_create(skills, ignore_conflicts=True)
    
    @staticmethod
    def update(skill_id, name=None, skill_type=None):
        skill = Skill.objects.get(id=skill_id)
        if name is not None:
            skill.name = name
        if skill_type is not None:
            skill.skill_type = skill_type
        skill.save()
        return skill
    
    @staticmethod
    def delete(skill_id):
        return Skill.objects.filter(id=skill_id).delete()


class VacancyRepository:
    @staticmethod
    def get_all():
        return Vacancy.objects.all()
    
    @staticmethod
    def get_by_id(vacancy_id):
        return Vacancy.objects.get(id_vacancy=vacancy_id)
    
    @staticmethod
    def create(**kwargs):
        return Vacancy.objects.create(**kwargs)
    
    @staticmethod
    def get_or_create(**kwargs):
        vacancy_id = kwargs.pop('id_vacancy')
        return Vacancy.objects.get_or_create(id_vacancy=vacancy_id, defaults=kwargs)
    
    @staticmethod
    def bulk_create(vacancies_data):
        vacancies = [Vacancy(**data) for data in vacancies_data]
        return Vacancy.objects.bulk_create(vacancies, ignore_conflicts=True)
    
    @staticmethod
    def update(vacancy_id, **kwargs):
        vacancy = Vacancy.objects.get(id_vacancy=vacancy_id)
        for key, value in kwargs.items():
            setattr(vacancy, key, value)
        vacancy.save()
        return vacancy
    
    @staticmethod
    def delete_old_vacancies():
        threshold = timezone.now() - timedelta(days=180)
        deleted, _ = Vacancy.objects.filter(fetched_at__lt=threshold).delete()
        return deleted

    @staticmethod
    def exists_for_job_target(job_target: JobTarget, region: str = None) -> bool:
        queryset = Vacancy.objects.filter(job_target=job_target)
        if region:
            queryset = queryset.filter(region__icontains=region)
        return queryset.exists()
    
    @staticmethod
    def get_existing_ids(id_list: List[str]) -> set:
        return set(Vacancy.objects.filter(id_vacancy__in=id_list).values_list('id_vacancy', flat=True))


class VacancySkillRepository:
    @staticmethod
    def get_all():
        return VacancySkill.objects.all()

    @staticmethod
    def get_or_create(vacancy, skill):
        return VacancySkill.objects.get_or_create(
            vacancy=vacancy,
            skill=skill
        )

    @staticmethod
    # Для массового создания связей вакансий и навыков (например, при загрузке из вакансий)
    def bulk_create(relations):
        objs = [VacancySkill(**rel) for rel in relations]
        return VacancySkill.objects.bulk_create(objs, ignore_conflicts=True)
    
    @staticmethod
    def get_skills_for_vacancy(vacancy_id):
        return VacancySkill.objects.filter(vacancy_id=vacancy_id).select_related('skill')
    
    @staticmethod
    def get_skill_importance_for_job_title(job_title: str, region: str = None):
        # Разбиваем job_title на слова и соединяем через ' & ' (логическое И)
        words = job_title.lower().replace('-', ' ').split()
        query_string = ' & '.join(words) 
        search_query = SearchQuery(query_string, config='russian')

        # Аннотируем вакансии поисковым вектором и фильтруем
        vacancies_qs = Vacancy.objects.annotate(
            search=SearchVector('title', config='russian')
        ).filter(search=search_query)

        if region:
            vacancies_qs = vacancies_qs.filter(region__icontains=region)

        # Теперь собираем навыки
        return VacancySkill.objects.filter(vacancy__in=vacancies_qs) \
            .values('skill') \
            .annotate(importance=Count('vacancy')) \
            .order_by('-importance')
    
    @staticmethod
    def get_global_skill_importance():
        return VacancySkill.objects.values('skill').annotate(importance=Count('vacancy')).order_by('-importance')


class SkillPrerequisiteRepository:
    @staticmethod
    def get_or_create(skill, prerequisite_skill):
        return SkillPrerequisite.objects.get_or_create(
            skill=skill,
            prerequisite_skill=prerequisite_skill
        )
    
    @staticmethod
    def bulk_create(prerequisites):
        objs = [SkillPrerequisite(**p) for p in prerequisites]
        return SkillPrerequisite.objects.bulk_create(objs, ignore_conflicts=True)
    
    @staticmethod
    def get_prerequisites(skill):
        return SkillPrerequisite.objects.filter(skill=skill).select_related('prerequisite_skill')
    
    @staticmethod
    def exists(prerequisite_skill: Skill, target_skill: Skill) -> bool:
        """Проверяет, существует ли связь prerequisite_skill → target_skill."""
        return SkillPrerequisite.objects.filter(
            skill=target_skill,
            prerequisite_skill=prerequisite_skill
        ).exists()

class JobTargetRepository:
    @staticmethod
    def get_or_create(name):
        return JobTarget.objects.get_or_create(name=name)

    @staticmethod
    def get_by_name(name):
        return JobTarget.objects.filter(name=name).first()
    
    @staticmethod
    def get_by_id(job_target_id):
        return JobTarget.objects.get(id=job_target_id)
    
    @staticmethod
    def get_active():
        return JobTarget.objects.filter(is_active=True)
    
    @staticmethod
    def delete(job_target_id):
        JobTarget.objects.filter(id=job_target_id).delete()

class UserTargetRepository:
    @staticmethod
    def get_for_user(user):
        return UserTarget.objects.filter(user=user).select_related('target_job')
    
    @staticmethod
    def create(user, target_job):
        return UserTarget.objects.create(user=user, target_job=target_job)
    
    @staticmethod
    def delete(target_id):
        return UserTarget.objects.filter(id=target_id).delete()
    
    @staticmethod
    def get_active_targets(user):
        return UserTarget.objects.filter(user=user)


class GeneratedPathRepository:
    @staticmethod
    def create_with_limit(user, target, is_current=False):
        MAX_PATHS_PER_USER = 10
        current_user_paths_number = GeneratedPath.objects.filter(user=user).count()
        if current_user_paths_number >= MAX_PATHS_PER_USER:
            oldest_path = GeneratedPath.objects.filter(user=user).exclude(is_current=True).order_by('generated_at').first()
            if oldest_path:
                oldest_path.delete()
            else:
                oldest_path = GeneratedPath.objects.filter(user=user).order_by('generated_at').first()
                if oldest_path:
                    oldest_path.delete()
        new_path = GeneratedPath.objects.create(user=user, target=target, is_current=is_current)
        if is_current:
            GeneratedPath.objects.filter(user=user, target=target, is_current=True).exclude(id=new_path.id).update(is_current=False)
        return new_path
    
    @staticmethod
    def get_current_for_target(user, target):
        return GeneratedPath.objects.filter(user=user, target=target, is_current=True).first()
    
    @staticmethod
    def get_history_for_user(user):
        return GeneratedPath.objects.filter(user=user).order_by('-generated_at')


class PathStepRepository:
    @staticmethod
    def create(path, skill, step_order):
        return PathStep.objects.create(
            generated_path=path,
            skill=skill,
            step_order=step_order
        )
    
    @staticmethod
    def bulk_create(steps):
        objs = [PathStep(**step) for step in steps]
        return PathStep.objects.bulk_create(objs)
    
    @staticmethod
    def get_for_path(path):
        return PathStep.objects.filter(generated_path=path).order_by('step_order')


class UserSkillRepository:
    @staticmethod
    def get_skills_for_user(user):
        return UserSkill.objects.filter(user=user).select_related('skill')
    
    @staticmethod
    def add_skill(user, skill):
        return UserSkill.objects.get_or_create(user=user, skill=skill)
    
    @staticmethod
    def remove_skill(user, skill):
        return UserSkill.objects.filter(user=user, skill=skill).delete()
    
    @staticmethod
    def bulk_add(user, skills):
        objs = [UserSkill(user=user, skill=skill) for skill in skills]
        return UserSkill.objects.bulk_create(objs, ignore_conflicts=True)
    