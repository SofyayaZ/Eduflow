from typing import List, Tuple
from core.models import User, Skill
from django.db.models import Q
import re
from core.services.ranking_service import RankingService
from core.repository import (
    UserSkillRepository, VacancySkillRepository,
    SkillRepository, VacancyRepository
)

class SkillMatchingService:
    @staticmethod
    def get_required_skills_for_target(target_job_title: str, region: str = None) -> List[Tuple[Skill, int]]:
        skills_importance = VacancySkillRepository.get_skill_importance_for_job_title(target_job_title, region=region)
        result = []
        for item in skills_importance:
            skill = SkillRepository.get_by_id(item['skill'])
            if skill:
                result.append((skill, item['importance']))
        return result

    @staticmethod
    def get_missing_skills(user: User, target_job_title: str) -> List[Tuple[Skill, int]]:
        user_skill_ids = set(
            UserSkillRepository.get_skills_for_user(user).values_list('skill_id', flat=True)
        )
        region = user.preferred_region if user.preferred_region else None
        required = SkillMatchingService.get_required_skills_for_target(target_job_title, region=region)
        return [(skill, imp) for skill, imp in required if skill.id not in user_skill_ids]
    
    @staticmethod
    def get_missing_skills_ranked(user: User, target_job_title: str):
        missing_pairs = SkillMatchingService.get_missing_skills(user, target_job_title)
        return RankingService.rank_skills_by_importance(missing_pairs)

    @staticmethod
    def has_vacancies_for_target(target_job_title: str, region: str = None) -> bool:
        return VacancyRepository.exists_by_title_icontains(target_job_title, region=region)
    