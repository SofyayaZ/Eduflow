from collections import deque
import logging
from typing import List, Set, Dict
from core.models import GeneratedPath, Skill, User, UserTarget
from core.repository import GeneratedPathRepository, PathStepRepository, SkillPrerequisiteRepository
from collections import deque


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
        skill_by_id = {s.id: s for s in skills}
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
    def build_tree(skills: List[Skill], user_skills: Set[int], importance: Dict[int, int] = None) -> List[Dict]:
        """
        Строит лес деревьев навыков на основе пререквизитов.
        importance: dict {skill_id: importance} для сортировки детей (по убыванию)
        Возвращает список корневых узлов, каждый узел:
        {
            'skill': Skill,
            'importance': int,
            'children': [...]
        }
        """
        if not skills:
            return []

        # Множество id переданных навыков для быстрого поиска
        skill_ids = {s.id for s in skills}
        # Сопоставление id -> объект Skill
        skill_by_id = {s.id: s for s in skills}
        # importance по умолчанию 0
        if importance is None:
            importance = {}

        # 1. Построить граф зависимостей (только внутри skills)
        #    children[parent_id] = list of child_ids (где parent - прямой пререквизит child)
        children = {sid: [] for sid in skill_ids}
        # Также запомним, какие навыки имеют родителей (чтобы потом найти корни)
        has_parent = set()

        for skill in skills:
            prereqs = SkillPrerequisiteRepository.get_prerequisites(skill)
            for prereq in prereqs:
                prereq_skill = prereq.prerequisite_skill
                if prereq_skill.id in skill_ids:
                    # Пререквизит есть в нашем списке -> строим ребро prereq -> skill
                    children[prereq_skill.id].append(skill.id)
                    has_parent.add(skill.id)
                elif prereq_skill.id not in user_skills:
                    # Пререквизит отсутствует и у пользователя, и в списке – это ошибка,
                    # так как _expand_missing_with_prerequisites должен был его добавить.
                    raise ValueError(
                        f"Prerequisite '{prereq_skill.name}' for skill '{skill.name}' "
                        f"is missing both in provided skills list and user skills."
                    )
                # Если пререквизит есть у пользователя – игнорируем (уже изучен, не входит в дерево)

        # 2. Корни – навыки, у которых нет родителей в нашем графе
        roots_ids = [sid for sid in skill_ids if sid not in has_parent]
        # Сортируем корни по важности (по убыванию) для предсказуемости
        roots_ids.sort(key=lambda sid: importance.get(sid, 0), reverse=True)

        # 3. Рекурсивная функция построения узла
        def build_node(skill_id: int) -> Dict:
            node_skill = skill_by_id[skill_id]
            # Дети – это навыки, для которых текущий является прямым пререквизитом
            child_ids = children.get(skill_id, [])
            # Сортируем детей по важности (убывание)
            child_ids.sort(key=lambda cid: importance.get(cid, 0), reverse=True)
            children_nodes = [build_node(cid) for cid in child_ids]
            return {
                'skill': {
                    'id': node_skill.id,
                    'name': node_skill.name,
                    # при необходимости можно добавить другие поля
                },
                'importance': importance.get(skill_id, 0),
                'children': children_nodes
            }

        # Строим лес
        forest = [build_node(root_id) for root_id in roots_ids]
        return forest


    @staticmethod
    def build_sequence(skills: List[Skill], user_skills: Set[int]) -> List[Skill]:
        """
        Упорядочивает переданные навыки с учётом пререквизитов.
        Предполагается, что список skills уже содержит все необходимые навыки
        (включая добавленные пререквизиты). Повторного расширения не происходит.
        """
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
    def _expand_missing_with_prerequisites(missing_skills: List[Skill], user_skills: Set[int]) -> List[Skill]:
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