from collections import deque
from typing import List, Set

from core.models import GeneratedPath, Skill, User, UserTarget
from core.repository import GeneratedPathRepository, PathStepRepository, SkillPrerequisiteRepository


class PathBuilder:
    @staticmethod
    def build_sequence(missing_skills: List[Skill], user_skills: Set[int]) -> List[Skill]:
        missing_ids = {skill.id for skill in missing_skills}

        graph = {skill.id: [] for skill in missing_skills}
        in_degree = {skill.id: 0 for skill in missing_skills}

        for skill in missing_skills:
            prereqs = SkillPrerequisiteRepository.get_prerequisites(skill)
            for prereq in prereqs:
                prereq_skill = prereq.prerequisite_skill
                if prereq_skill.id in missing_ids:
                    graph[prereq_skill.id].append(skill.id)
                    in_degree[skill.id] += 1
                elif prereq_skill.id not in user_skills:
                    raise ValueError(f"User is missing prerequisite skill {prereq_skill.name} for {skill.name}")

        # Топологическая сортировка   
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        result_ids = []
        while queue:
            sid = queue.popleft()
            result_ids.append(sid)
            for neighbor in graph[sid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result_ids) != len(missing_skills):
            raise ValueError("There is a cycle in the skill prerequisites")
        
        id_to_skill = {skill.id: skill for skill in missing_skills}
        return [id_to_skill[sid] for sid in result_ids]

    @staticmethod
    def create_path(user : User, target : UserTarget, skills_sequence : List[Skill]) -> GeneratedPath:
        path = GeneratedPathRepository.create_with_limit(user=user, target=target, is_current=True)
        for order, skill in enumerate(skills_sequence, start=1):
            PathStepRepository.create(path, skill, order)
        return path

