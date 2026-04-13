from typing import List
from typing import Tuple
from core.models import Skill


class RankingService:
    @staticmethod
    def rank_skills_by_importance(missing_skills : List[Tuple[Skill, int]]) -> List[Skill]:
        sorted_skills = sorted(missing_skills, key=lambda x: x[1], reverse=True)
        return [skill for skill, _ in sorted_skills]
