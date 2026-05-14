from collections import deque
import logging
from typing import List, Set, Dict
from core.models import GeneratedPath, Skill, User, UserTarget
from core.repository import GeneratedPathRepository, PathStepRepository, SkillPrerequisiteRepository
from collections import deque

from core.services.ranking_service import RankingService


logger = logging.getLogger(__name__)


class PathBuilder:
    @staticmethod
    def build_graph(skills: List[Skill], user_skills: Set[int], importance: Dict[int, int] = None) -> Dict:
        """
        Строит граф навыков в формате {nodes: [...], edges: [...]}.
        Каждый узел: { id, data: { label, importance }, position: { x, y } (позже заполнит фронт) }
        Каждое ребро: { id, source, target, animated, style }
        """
        if not skills:
            return {'nodes': [], 'edges': []}

        skill_ids = {s.id for s in skills}
        if importance is None:
            importance = {}

        # Построение списка рёбер (на основе прямых пререквизитов)
        edges = []
        added_edges = set()  # чтобы избежать дублирования

        for skill in skills:
            prereqs = SkillPrerequisiteRepository.get_prerequisites(skill)
            for prereq in prereqs:
                prereq_skill = prereq.prerequisite_skill
                if prereq_skill.id in skill_ids:
                    edge_id = f"{prereq_skill.id}-{skill.id}"
                    if edge_id not in added_edges:
                        added_edges.add(edge_id)
                        edges.append({
                            'id': edge_id,
                            'source': str(prereq_skill.id),
                            'target': str(skill.id),
                            'animated': True,
                            'style': {'stroke': '#1a5f9c', 'strokeWidth': 2}
                        })
                elif prereq_skill.id not in user_skills:
                    raise ValueError(
                        f"Prerequisite '{prereq_skill.name}' for skill '{skill.name}' "
                        f"is missing both in provided skills list and user skills."
                    )

        # Создание узлов
        nodes = []
        for skill in skills:
            nodes.append({
                'id': str(skill.id),
                'data': {
                    'label': skill.name,
                    'importance': importance.get(skill.id, 0)
                },
                'position': {'x': 0, 'y': 0},  # позиции будут пересчитаны на фронтенде через dagre
                'style': {
                    'background': '#FFF',
                    'border': '1px solid #1a5f9c',
                    'borderRadius': '8px',
                    'padding': '10px'
                }
            })

        return {'nodes': nodes, 'edges': edges}
    
    @staticmethod
    def build_full_graph_with_standalone(
        all_hard_tool_skills: List[Skill], 
        user_skills: Set[int], 
        importance: Dict[int, int]
    ) -> Dict:
        # строим полный граф
        full_graph = PathBuilder.build_graph(all_hard_tool_skills, user_skills, importance)
        # вычисляем, какие узлы имеют рёбра
        nodes_with_edges = set()
        for edge in full_graph['edges']:
            nodes_with_edges.add(edge['source'])
            nodes_with_edges.add(edge['target'])
        connected_skills = []
        standalone_skills = []
        for skill in all_hard_tool_skills:
            if str(skill.id) in nodes_with_edges:
                connected_skills.append(skill)
            else:
                standalone_skills.append(skill)
        # строим граф только для связанных, если они есть
        if connected_skills:
            graph = PathBuilder.build_graph(connected_skills, user_skills, importance)
        else:
            graph = {'nodes': [], 'edges': []}
        return {
            'graph': graph,
            'standalone_skills': standalone_skills
        }

    @staticmethod
    def build_sequence(skills: List[Skill], user_skills: Set[int]) -> List[Skill]:
        # Множество id переданных навыков
        skills_ids = {s.id for s in skills}

        # Строим граф и степени входа
        graph = {skill.id: [] for skill in skills}
        in_degree = {skill.id: 0 for skill in skills}

        for skill in skills:
            prereqs = SkillPrerequisiteRepository.get_prerequisites(skill)
            for prereq in prereqs:
                prereq_skill = prereq.prerequisite_skill
                if prereq_skill.id in skills_ids:
                    # Зависимость внутри переданного списка
                    graph[prereq_skill.id].append(skill.id)
                    in_degree[skill.id] += 1
                elif prereq_skill.id not in user_skills:
                    # Пререквизит отсутствует и у пользователя, и в списке – ошибка
                    raise ValueError(
                        f"Prerequisite '{prereq_skill.name}' for skill '{skill.name}' "
                        f"is missing both in provided skills list and user skills."
                    )
                # Если пререквизит есть у пользователя – просто игнорируем (уже изучен)

        # Топологическая сортировка (алгоритм Кана)
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        result_ids = []
        while queue:
            sid = queue.popleft()
            result_ids.append(sid)
            for neighbor in graph[sid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result_ids) != len(skills):
            raise ValueError("Cycle detected in skill prerequisites")

        id_to_skill = {skill.id: skill for skill in skills}
        return [id_to_skill[sid] for sid in result_ids]
    
    @staticmethod
    def expand_missing_with_prerequisites(missing_skills: List[Skill], user_skills: Set[int]) -> List[Skill]:
        """
        Расширяет список недостающих навыков, добавляя все необходимые 
        транзитивные пререквизиты, которые отсутствуют у пользователя.
        Возвращает новый список навыков (включая добавленные).
        """
        # Работаем с множеством для быстрого поиска
        missing_set = set(missing_skills)
        processed = set()
        changed = True
        iteration = 0
        max_iterations = 100  # защита от бесконечного цикла
        
        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            for skill in list(missing_set):
                if skill.id in processed:
                    continue
                processed.add(skill.id)
                prereqs = SkillPrerequisiteRepository.get_prerequisites(skill)
                for prereq in prereqs:
                    prereq_skill = prereq.prerequisite_skill
                    if prereq_skill.pk is None:
                        logger.warning(f"Prerequisite '{prereq_skill.name}' has no pk, skipping")
                        continue
                    if not Skill.objects.filter(id=prereq_skill.id).exists():
                        logger.warning(f"Prerequisite '{prereq_skill.name}' (id={prereq_skill.id}) does not exist in Skills table, skipping")
                        continue
                    if prereq_skill.id not in user_skills and prereq_skill not in missing_set:
                        missing_set.add(prereq_skill)
                        changed = True
                        logger.info(f"Auto-added missing prerequisite '{prereq_skill.name}' for '{skill.name}'")
        
        if iteration >= max_iterations:
            logger.warning("Maximum iterations reached while expanding prerequisites")
        
        # Преобразуем обратно в список (сохраняем порядок исходных навыков в начале)
        # Сначала идут исходные missing_skills, затем добавленные (уникальные)
        original_ids = {s.id for s in missing_skills}
        added_skills = [s for s in missing_set if s.id not in original_ids]
        # Добавленные навыки можно отсортировать по имени для предсказуемости
        added_skills.sort(key=lambda s: s.name)
        
        # Возвращаем список: исходные (в исходном порядке) + добавленные
        result = list(missing_skills) + added_skills
        return result
    

    @staticmethod
    def create_path(user : User, target : UserTarget, skills_sequence : List[Skill]) -> GeneratedPath:
        path = GeneratedPathRepository.create_with_limit(user=user, target=target, is_current=True)
        for order, skill in enumerate(skills_sequence, start=1):
            PathStepRepository.create(path, skill, order)
        return path
    
    @staticmethod
    def build_full_path(missing_skills: List[Skill],
                        importance: Dict[int, int],
                        user_skills: Set[int],
                        max_steps: int = 10) -> List[Skill]:
        """
        Полностью строит траекторию обучения:
        """
        # 1. Расширяем пререквизитами
        expanded = PathBuilder.expand_missing_with_prerequisites(missing_skills, user_skills)
        
        # 2. Ранжируем по важности
        pairs = [(skill, importance.get(skill.id, 0)) for skill in expanded]
        ranked = RankingService.rank_skills_by_importance(pairs)   # List[Skill]
        
        # 3. Топологическая сортировка
        full_sequence = PathBuilder.build_sequence(ranked, user_skills)
        
        # 4. Обрезаем до max_steps
        return full_sequence[:max_steps]
    