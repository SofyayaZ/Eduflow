import pytest
from unittest.mock import Mock, patch
from core.services.path_builder import PathBuilder
from core.models import Skill


class TestPathBuilder:
    
    # -------------------- build_graph --------------------
    def test_build_graph_missing_prerequisite(self, skill_python, skill_django):
        """Пререквизит отсутствует и в списке, и у пользователя."""
        missing_skill = Mock(spec=Skill)
        missing_skill.id = 99
        missing_skill.name = "Missing"
        prereq_mock = Mock()
        prereq_mock.prerequisite_skill = missing_skill
        
        with patch('core.services.path_builder.SkillPrerequisiteRepository.get_prerequisites') as mock_get:
            # Для обоих навыков возвращаем один и тот же отсутствующий пререквизит
            mock_get.return_value = [prereq_mock]
            # Ожидаем, что ошибка возникнет для первого навыка в списке (skill_python)
            with pytest.raises(ValueError, match="Prerequisite 'Missing' for skill 'Python' is missing"):
                PathBuilder.build_graph([skill_python, skill_django], set(), {})

    def test_build_sequence_missing_prerequisite(self, skill_python, skill_django):
        """build_sequence также должен кидать ошибку."""
        missing_skill = Mock(spec=Skill)
        missing_skill.id = 99
        missing_skill.name = "Missing"
        prereq_mock = Mock()
        prereq_mock.prerequisite_skill = missing_skill
        
        with patch('core.services.path_builder.SkillPrerequisiteRepository.get_prerequisites') as mock_get:
            mock_get.return_value = [prereq_mock]
            with pytest.raises(ValueError, match="Prerequisite 'Missing' for skill 'Python' is missing"):
                PathBuilder.build_sequence([skill_python, skill_django], set())

    # -------------------- _expand_missing_with_prerequisites (требует БД) --------------------

    @pytest.mark.django_db
    def test_expand_missing_no_prerequisites(self, skill_python):
        with patch('core.services.path_builder.SkillPrerequisiteRepository.get_prerequisites') as mock_get:
            mock_get.return_value = []
            result = PathBuilder._expand_missing_with_prerequisites([skill_python], set())
            assert result == [skill_python]

    @pytest.mark.django_db
    def test_expand_missing_adds_direct_prerequisite(self, skill_python, skill_django):
        """Django требует Python, Python отсутствует у пользователя -> добавляем."""
        prereq_mock = Mock()
        prereq_mock.prerequisite_skill = skill_python
        with patch('core.services.path_builder.SkillPrerequisiteRepository.get_prerequisites') as mock_get:
            mock_get.return_value = [prereq_mock]  # для skill_django
            result = PathBuilder._expand_missing_with_prerequisites([skill_django], set())
            # Результат: сначала исходный (skill_django), затем добавленный (skill_python)
            assert len(result) == 2
            assert result[0] == skill_django
            assert result[1] == skill_python

    @pytest.mark.django_db
    def test_expand_missing_transitive(self, skill_python, skill_django, skill_postgresql):
        """PostgreSQL требует Django, Django требует Python – должны добавиться оба."""
        # PostgreSQL -> Django, Django -> Python
        prereq_pg_django = Mock(prerequisite_skill=skill_django)
        prereq_django_python = Mock(prerequisite_skill=skill_python)
        
        def get_prereqs(skill):
            if skill == skill_postgresql:
                return [prereq_pg_django]
            if skill == skill_django:
                return [prereq_django_python]
            return []
        
        with patch('core.services.path_builder.SkillPrerequisiteRepository.get_prerequisites') as mock_get:
            mock_get.side_effect = get_prereqs
            result = PathBuilder._expand_missing_with_prerequisites([skill_postgresql], set())
            # Должны быть все три навыка: PostgreSQL (исходный), Django, Python
            assert {s.id for s in result} == {skill_postgresql.id, skill_django.id, skill_python.id}
            # Порядок: исходный первый, остальные отсортированы по имени
            assert result[0] == skill_postgresql
            added = sorted(result[1:], key=lambda s: s.name)
            assert added == [skill_django, skill_python]  # по имени: Django, Python

    @pytest.mark.django_db
    def test_expand_missing_skips_existing_user_skills(self, skill_python, skill_django):
        """Python уже есть у пользователя – не добавляем."""
        prereq_mock = Mock(prerequisite_skill=skill_python)
        with patch('core.services.path_builder.SkillPrerequisiteRepository.get_prerequisites') as mock_get:
            mock_get.return_value = [prereq_mock]
            result = PathBuilder._expand_missing_with_prerequisites([skill_django], {skill_python.id})
            assert result == [skill_django]  # Python не добавлен

    @pytest.mark.django_db
    def test_expand_missing_max_iterations(self, skill_python):
        """Искусственный цикл (самоссылка) – метод не зависает."""
        # Создаём пререквизит, который ссылается на самого себя
        prereq_self = Mock(prerequisite_skill=skill_python)
        with patch('core.services.path_builder.SkillPrerequisiteRepository.get_prerequisites') as mock_get:
            mock_get.return_value = [prereq_self]
            with patch('core.services.path_builder.logger') as mock_logger:
                result = PathBuilder._expand_missing_with_prerequisites([skill_python], set())
                # Ничего не должно добавиться
                assert result == [skill_python]
                # Предупреждение не вызывается, так как нет новых навыков - итераций нет
                mock_logger.warning.assert_not_called()
