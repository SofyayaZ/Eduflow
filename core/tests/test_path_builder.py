import pytest
from unittest.mock import Mock, patch
from core.models import GeneratedPath, JobTarget, PathStep, Skill, SkillPrerequisite, UserTarget
from core.services.path_builder import PathBuilder


def test_build_sequence_with_prerequisites():
    skill_a = Skill(id=1, name='A')
    skill_b = Skill(id=2, name='B')
    with patch('core.repository.SkillPrerequisiteRepository.get_prerequisites') as mock:
        mock.side_effect = lambda skill: [Mock(prerequisite_skill=skill_a)] if skill.id==2 else []
        sequence = PathBuilder.build_sequence([skill_a, skill_b], user_skills=set())
        assert [s.name for s in sequence] == ['A', 'B']
        
def test_build_sequence_missing_prerequisites():
    skill_a = Skill(id=1, name='A')
    skill_b = Skill(id=2, name='B')
    # B требует A, но A нет ни у пользователя, но в списке недостающих навыков
    with patch('core.repository.SkillPrerequisiteRepository.get_prerequisites') as mock:
        mock.return_value = [Mock(prerequisite_skill=skill_a)]
        with pytest.raises(ValueError, match="missing prerequisite skill A for B"):
            PathBuilder.build_sequence([skill_b], user_skills=set())

@pytest.mark.django_db
def test_build_sequence_with_real_db(skills):
    SkillPrerequisite.objects.create(skill=skills['django'], prerequisite_skill=skills['python'])
    SkillPrerequisite.objects.create(skill=skills['sql'], prerequisite_skill=skills['django'])
    missing_skills = [skills['django'], skills['sql']]
    user_skills = {skills['python'].id}
    sequence = PathBuilder.build_sequence(missing_skills, user_skills)
    assert [skill.name for skill in sequence]==['Django', 'SQL']

@pytest.mark.django_db
def test_create_path(test_user, user_target, skills):
    sequence = [skills['django'], skills['sql']]  # список объектов Skill
    PathBuilder.create_path(test_user, user_target, sequence)
    assert GeneratedPath.objects.count() == 1
    assert PathStep.objects.count() == 2
    steps = PathStep.objects.order_by('step_order')
    assert steps[0].skill.name == 'Django'
    assert steps[1].skill.name == 'SQL'
