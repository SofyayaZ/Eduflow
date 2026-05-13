from typing import List, Tuple
from core.models import JobTarget, User, Skill
from core.repository import (
    UserSkillRepository, VacancySkillRepository,
    SkillRepository, VacancyRepository
)


class SkillMatchingService:
    @staticmethod
    def get_required_skills_for_target(job_target_title: str, region: str = None, min_freq: int = 3) -> List[Tuple[Skill, int]]:
        skills_importance = VacancySkillRepository.get_skill_importance_for_job_title(job_target_title, region=region)
        result = []
        for item in skills_importance:
            if item['importance'] < min_freq:
                continue
            skill = SkillRepository.get_by_id(item['skill'])
            if skill:
                result.append((skill, item['importance']))
        return result

    @staticmethod
    def get_missing_skills(user: User, job_target_title: str) -> List[Tuple[Skill, int]]:
        user_skill_ids = set(
            UserSkillRepository.get_skills_for_user(user).values_list('skill_id', flat=True)
        )
        region = user.preferred_region if user.preferred_region else None
        required = SkillMatchingService.get_required_skills_for_target(job_target_title, region=region)
        return [(skill, imp) for skill, imp in required if skill.id not in user_skill_ids]

    @staticmethod
    def has_vacancies_for_target(job_target: JobTarget, region: str = None) -> bool:
        return VacancyRepository.exists_for_job_target(job_target, region=region)
    