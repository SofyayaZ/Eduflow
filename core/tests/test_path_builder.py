import pytest
from unittest.mock import patch, Mock
from core.models import Skill, SkillPrerequisite
from core.services.path_builder import PathBuilder


# ========== Тесты для _expand_missing_with_prerequisites ==========

@pytest.mark.django_db
def test_expand_adds_missing_prerequisite(skills):
    """Если у навыка есть prerequisite, которого нет у пользователя и нет в missing_skills,
    он должен быть автоматически добавлен."""
    SkillPrerequisite.objects.create(
        skill=skills['django'],
        prerequisite_skill=skills['python']
    )
    missing = [skills['django']]
    user_skills = set()  # у пользователя нет python

    expanded = PathBuilder._expand_missing_with_prerequisites(missing, user_skills)

    assert len(expanded) == 2
    assert skills['django'] in expanded
    assert skills['python'] in expanded
    # Исходный навык идёт первым
    assert expanded[0] == skills['django']


@pytest.mark.django_db
def test_expand_does_not_add_existing_user_skill(skills):
    """Если prerequisite уже есть у пользователя, он не добавляется в expanded."""
    SkillPrerequisite.objects.create(
        skill=skills['django'],
        prerequisite_skill=skills['python']
    )
    missing = [skills['django']]
    user_skills = {skills['python'].id}

    expanded = PathBuilder._expand_missing_with_prerequisites(missing, user_skills)

    assert len(expanded) == 1
    assert expanded[0] == skills['django']


@pytest.mark.django_db
def test_expand_does_not_add_existing_missing_skill(skills):
    """Если prerequisite уже есть в missing_skills, он не дублируется."""
    SkillPrerequisite.objects.create(
        skill=skills['django'],
        prerequisite_skill=skills['python']
    )
    missing = [skills['django'], skills['python']]
    user_skills = set()

    expanded = PathBuilder._expand_missing_with_prerequisites(missing, user_skills)

    assert len(expanded) == 2
    assert expanded[0] == skills['django']
    assert expanded[1] == skills['python']


@pytest.mark.django_db
def test_expand_transitive_prerequisites(skills):
    """Транзитивные зависимости: A требует B, B требует C → добавляются и B, и C."""
    SkillPrerequisite.objects.create(skill=skills['sql'], prerequisite_skill=skills['django'])
    SkillPrerequisite.objects.create(skill=skills['django'], prerequisite_skill=skills['python'])
    missing = [skills['sql']]
    user_skills = set()

    expanded = PathBuilder._expand_missing_with_prerequisites(missing, user_skills)

    assert len(expanded) == 3
    assert expanded[0] == skills['sql']
    # Добавленные сортируются по имени
    added = expanded[1:]
    assert set(added) == {skills['django'], skills['python']}


@pytest.mark.django_db
def test_expand_order_preserves_original_and_sorts_added(skills):
    """Исходные навыки остаются в своём порядке, добавленные сортируются по имени."""
    SkillPrerequisite.objects.create(skill=skills['sql'], prerequisite_skill=skills['python'])
    SkillPrerequisite.objects.create(skill=skills['django'], prerequisite_skill=skills['java'])
    missing = [skills['django'], skills['sql']]  # порядок: Django, SQL
    user_skills = set()

    expanded = PathBuilder._expand_missing_with_prerequisites(missing, user_skills)

    # Исходные: Django, SQL
    assert expanded[:2] == [skills['django'], skills['sql']]
    # Добавленные: java, python (сортировка по имени)
    added = expanded[2:]
    assert len(added) == 2
    assert added[0].name < added[1].name  # java < python
    assert {s.name for s in added} == {'Java', 'Python'}


@pytest.mark.django_db
def test_expand_no_prerequisites_no_change(skills):
    """Если нет ни одного prerequisite, список не меняется."""
    missing = [skills['python'], skills['java']]
    user_skills = set()

    expanded = PathBuilder._expand_missing_with_prerequisites(missing, user_skills)

    assert len(expanded) == 2
    assert expanded == missing


# ========== Тесты для build_sequence (с расширением) ==========

@pytest.mark.django_db
def test_build_sequence_auto_adds_prerequisite(skills):
    """build_sequence автоматически добавляет недостающий prerequisite и строит корректный порядок."""
    SkillPrerequisite.objects.create(skill=skills['django'], prerequisite_skill=skills['python'])
    missing = [skills['django']]
    user_skills = set()  # у пользователя нет python

    sequence = PathBuilder.build_sequence(missing, user_skills)

    # Ожидаемый порядок: сначала python, потом django (т.к. python – prerequisite)
    assert [s.name for s in sequence] == ['Python', 'Django']


@pytest.mark.django_db
def test_build_sequence_with_transitive_prerequisites(skills):
    """Транзитивные зависимости: SQL требует Django, Django требует Python.
    У пользователя нет ничего → порядок: Python → Django → SQL."""
    SkillPrerequisite.objects.create(skill=skills['django'], prerequisite_skill=skills['python'])
    SkillPrerequisite.objects.create(skill=skills['sql'], prerequisite_skill=skills['django'])
    missing = [skills['sql']]
    user_skills = set()

    sequence = PathBuilder.build_sequence(missing, user_skills)

    assert [s.name for s in sequence] == ['Python', 'Django', 'SQL']


@pytest.mark.django_db
def test_build_sequence_with_partial_user_skills(skills):
    """У пользователя уже есть часть prerequisite, недостающие добавляются."""
    SkillPrerequisite.objects.create(skill=skills['django'], prerequisite_skill=skills['python'])
    SkillPrerequisite.objects.create(skill=skills['sql'], prerequisite_skill=skills['django'])
    missing = [skills['sql']]
    user_skills = {skills['python'].id}  # python уже знает

    sequence = PathBuilder.build_sequence(missing, user_skills)

    # Нужен только Django (т.к. Python уже есть), порядок: Django → SQL
    assert [s.name for s in sequence] == ['Django', 'SQL']


@pytest.mark.django_db
def test_build_sequence_cycle_detection(skills):
    """При наличии цикла в графе prerequisite выбрасывается ValueError."""
    # Создаём цикл: A -> B -> A
    SkillPrerequisite.objects.create(skill=skills['django'], prerequisite_skill=skills['python'])
    SkillPrerequisite.objects.create(skill=skills['python'], prerequisite_skill=skills['django'])
    missing = [skills['django'], skills['python']]
    user_skills = set()

    with pytest.raises(ValueError, match="Cycle detected in skill prerequisites"):
        PathBuilder.build_sequence(missing, user_skills)


@pytest.mark.django_db
def test_build_sequence_extra_protection_raises(skills):
    """Если после расширения всё равно остался prerequisite, которого нет у пользователя и не в expanded,
    выбрасывается ValueError (защита от ошибок)."""
    # Создаём связь, но намеренно не включаем prerequisite в missing_skills
    SkillPrerequisite.objects.create(skill=skills['django'], prerequisite_skill=skills['python'])
    missing = [skills['django']]
    user_skills = set()
    # Мокаем _expand_missing_with_prerequisites, чтобы он не добавил python
    with patch.object(PathBuilder, '_expand_missing_with_prerequisites',
                      return_value=missing):
        with pytest.raises(ValueError, match="missing both in user skills and expanded list"):
            PathBuilder.build_sequence(missing, user_skills)


# ========== Интеграционный тест: create_path без изменений ==========

@pytest.mark.django_db
def test_create_path_with_expanded_skills(test_user, user_target, skills):
    """Проверка, что create_path работает с последовательностью, содержащей добавленные навыки."""
    # Создаём последовательность, включающую добавленные навыки
    sequence = [skills['python'], skills['django'], skills['sql']]
    path = PathBuilder.create_path(test_user, user_target, sequence)
    assert path is not None
    steps = list(path.steps.order_by('step_order'))
    assert len(steps) == 3
    assert steps[0].skill == skills['python']
    assert steps[1].skill == skills['django']
    assert steps[2].skill == skills['sql']