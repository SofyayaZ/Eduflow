import pytest
from unittest.mock import Mock, call, patch
from core.services.prerequisite_extractor import PrerequisiteExtractor
from core.models import Skill


@pytest.fixture
def extractor():
    """Создаёт экземпляр PrerequisiteExtractor с замоканными API и кэшем."""
    with patch('core.services.prerequisite_extractor.cache') as mock_cache, \
         patch('core.services.prerequisite_extractor.settings.DEEPSEEK_API_URL', 'https://fake.api'), \
         patch('core.services.prerequisite_extractor.settings.DEEPSEEK_API_KEY', 'fake_key'):
        mock_cache.get.return_value = None
        mock_cache.set.return_value = None
        extractor = PrerequisiteExtractor()
        extractor._call_api = Mock()
        return extractor


@pytest.fixture
def skill_python():
    skill = Mock(spec=Skill)
    skill.name = "Python"
    skill.skill_type = Skill.SkillType.HARD
    skill.id = 1
    return skill


@pytest.fixture
def skill_django():
    skill = Mock(spec=Skill)
    skill.name = "Django"
    skill.skill_type = Skill.SkillType.TOOL
    skill.id = 2
    return skill


@pytest.fixture
def skill_sql():
    skill = Mock(spec=Skill)
    skill.name = "SQL"
    skill.skill_type = Skill.SkillType.TOOL
    skill.id = 3
    return skill


@pytest.fixture
def skill_soft():
    skill = Mock(spec=Skill)
    skill.name = "Teamwork"
    skill.skill_type = Skill.SkillType.SOFT
    skill.id = 4
    return skill


class TestPrerequisiteExtractor:
    """Тесты для PrerequisiteExtractor."""

    # -------------------- _check_bidirectional --------------------

    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_check_bidirectional_from_map(self, mock_repo, extractor, skill_python, skill_django):
        """Проверка связи из словаря (Django -> Python)."""
        a_to_b, b_to_a = extractor._check_bidirectional(skill_django, skill_python)
        assert a_to_b is True   # Django требует Python
        assert b_to_a is False  # Python не требует Django
        # API не должен вызываться
        extractor._call_api.assert_not_called()

    @patch('core.services.prerequisite_extractor.cache')
    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_check_bidirectional_cache_hit(self, mock_repo, mock_cache, extractor, skill_python, skill_django):
        """Кэш возвращает предварительно сохранённый результат."""
        mock_cache.get.return_value = (True, False)
        a_to_b, b_to_a = extractor._check_bidirectional(skill_python, skill_django)
        assert a_to_b is True
        assert b_to_a is False
        extractor._call_api.assert_not_called()
        mock_cache.get.assert_called_once_with("prereq_pair:Python|Django")

    @patch('core.services.prerequisite_extractor.cache')
    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_check_bidirectional_llm_success(self, mock_repo, mock_cache, extractor, skill_python, skill_django):
        """Успешный вызов LLM, результат сохраняется в кэш."""
        mock_cache.get.return_value = None
        extractor._call_api.return_value = "да, нет"
        a_to_b, b_to_a = extractor._check_bidirectional(skill_python, skill_django)
        assert a_to_b is True
        assert b_to_a is False
        extractor._call_api.assert_called_once()
        mock_cache.set.assert_called_once_with("prereq_pair:Python|Django", (True, False), timeout=60*60*24*30)

    @patch('core.services.prerequisite_extractor.cache')
    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_check_bidirectional_llm_both_true(self, mock_repo, mock_cache, extractor, skill_python, skill_django):
        """LLM возвращает 'да, да' – игнорируем (защита от циклов)."""
        mock_cache.get.return_value = None
        extractor._call_api.return_value = "да, да"
        a_to_b, b_to_a = extractor._check_bidirectional(skill_python, skill_django)
        assert a_to_b is False
        assert b_to_a is False
        # В лог должно быть предупреждение, проверим через logger (опционально)

    @patch('core.services.prerequisite_extractor.cache')
    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_check_bidirectional_llm_invalid_format(self, mock_repo, mock_cache, extractor, skill_python, skill_django):
        """LLM возвращает неожиданный формат – fallback."""
        mock_cache.get.return_value = None
        extractor._call_api.return_value = "фылотдлфдл"  # не "да, нет"
        a_to_b, b_to_a = extractor._check_bidirectional(skill_python, skill_django)
        # Ищем слово "да" во всём ответе, если его нет, то False
        assert a_to_b is False
        assert b_to_a is False

    @patch('core.services.prerequisite_extractor.cache')
    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_check_bidirectional_llm_exception(self, mock_repo, mock_cache, extractor, skill_python, skill_django):
        """Ошибка при вызове API -> возвращаем (False, False)."""
        mock_cache.get.return_value = None
        extractor._call_api.side_effect = Exception("API error")
        a_to_b, b_to_a = extractor._check_bidirectional(skill_python, skill_django)
        assert a_to_b is False
        assert b_to_a is False

    # -------------------- extract_and_save_prerequisites --------------------

    def test_extract_and_save_no_skills(self, extractor):
        """Пустой список – ничего не делаем."""
        result = extractor.extract_and_save_prerequisites([])
        assert result == 0

    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_extract_and_save_skip_soft_skills(self, mock_repo, extractor, skill_python, skill_soft):
        """Пары с soft-навыками пропускаются."""
        result = extractor.extract_and_save_prerequisites([skill_python, skill_soft])
        assert result == 0
        mock_repo.get_or_create.assert_not_called()

    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_extract_and_save_one_way_dependency(self, mock_repo, extractor, skill_python, skill_django):
        """Односторонняя зависимость: Python -> Django."""
        # Мокаем _check_bidirectional, чтобы вернуть (True, False) для пары (Python, Django)
        extractor._check_bidirectional = Mock(return_value=(True, False))
        mock_repo.exists.return_value = False
        mock_repo.get_or_create.return_value = (Mock(), True)

        result = extractor.extract_and_save_prerequisites([skill_python, skill_django])
        assert result == 1
        # Проверяем, что существование обратной связи проверялось с правильным порядком
        mock_repo.exists.assert_called_once_with(skill_django, skill_python)
        # Проверяем, что связь создана как skill_a -> skill_b (Python -> Django)
        mock_repo.get_or_create.assert_called_once_with(skill_python, skill_django)

    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_extract_and_save_both_ways_detected(self, mock_repo, extractor, skill_python, skill_django):
        """Метод обнаружил оба направления – не сохраняет ничего."""
        extractor._check_bidirectional = Mock(return_value=(True, True))
        result = extractor.extract_and_save_prerequisites([skill_python, skill_django])
        assert result == 0
        mock_repo.get_or_create.assert_not_called()

    @patch('core.services.prerequisite_extractor.SkillPrerequisiteRepository')
    def test_extract_and_save_reverse_link_exists(self, mock_repo, extractor, skill_python, skill_django):
        """Обратная связь уже существует – пропускаем создание."""
        extractor._check_bidirectional = Mock(return_value=(True, False))
        mock_repo.exists.return_value = True  # связь B->A уже есть
        result = extractor.extract_and_save_prerequisites([skill_python, skill_django])
        assert result == 0
        mock_repo.get_or_create.assert_not_called()

    # -------------------- _parse_bidirectional_answer --------------------

    def test_parse_bidirectional_answer_ok(self, extractor):
        """Корректный ответ 'да, нет'."""
        a, b = extractor._parse_bidirectional_answer("да, нет", "A", "B")
        assert a is True
        assert b is False

    def test_parse_bidirectional_answer_both_true(self, extractor):
        """Ответ 'да, да' – оба False."""
        a, b = extractor._parse_bidirectional_answer("да, да", "A", "B")
        assert a is False
        assert b is False

    def test_parse_bidirectional_answer_unexpected_format(self, extractor):
        """Неожиданный формат – fallback."""
        with patch('core.services.prerequisite_extractor.logger') as mock_logger:
            a, b = extractor._parse_bidirectional_answer("yes and no", "A", "B")
            assert a is False  # 'да' не найдено
            assert b is False
            mock_logger.warning.assert_called_once()

    # -------------------- _build_bidirectional_prompt --------------------

    def test_build_bidirectional_prompt(self, extractor):
        prompt = extractor._build_bidirectional_prompt("Python", "Django")
        assert "Python" in prompt
        assert "Django" in prompt
        assert "да/нет" in prompt
        