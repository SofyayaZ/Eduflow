from typing import List
from typing import Tuple
from core.models import Skill


class RankingService:
    @staticmethod
    def rank_skills_by_importance(skills_or_pairs):
        if not skills_or_pairs:
            return []
        # Если передан список кортежей (Skill, int)
        if isinstance(skills_or_pairs[0], tuple):
            sorted_pairs = sorted(skills_or_pairs, key=lambda x: x[1], reverse=True)
            return [skill for skill, _ in sorted_pairs]
        # Если передан список Skill (без важности) — вернуть как есть
        return skills_or_pairs
