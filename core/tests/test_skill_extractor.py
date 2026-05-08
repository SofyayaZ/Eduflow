import pytest
from unittest.mock import Mock, patch
from core.services.skill_extractor import SkillExtractor


@pytest.fixture
def extractor():
    """Создаёт экземпляр SkillExtractor с мокнутым API."""
    with patch('core.services.skill_extractor.requests.post') as mock_post, \
         patch('core.services.skill_extractor.settings.DEEPSEEK_API_URL', 'https://fake.api'), \
         patch('core.services.skill_extractor.settings.DEEPSEEK_API_KEY', 'fake_key'):
        extractor = SkillExtractor()
        extractor._call_api = Mock()
        return extractor


class TestSkillExtractor:
    def test_extract_empty_text(self, extractor):
        assert extractor.extract("") == []
        assert extractor.extract("   ") == []
        extractor._call_api.assert_not_called()

    def test_extract_success(self, extractor):
        # Мокаем ответ API
        extractor._call_api.return_value = "Python, SQL, Docker"
        result = extractor.extract("Some description with Python and SQL")
        assert result == ["Python", "SQL", "Docker"]
        extractor._call_api.assert_called_once()

    def test_extract_with_extra_spaces(self, extractor):
        extractor._call_api.return_value = "  Python ,  SQL ,  Docker  "
        result = extractor.extract("text")
        assert result == ["Python", "SQL", "Docker"]

    def test_extract_api_failure(self, extractor):
        extractor._call_api.side_effect = Exception("API error")
        result = extractor.extract("some text")
        assert result == []
        extractor._call_api.assert_called_once()

    def test_extract_empty_result_from_api(self, extractor):
        extractor._call_api.return_value = ""
        result = extractor.extract("text")
        assert result == []

    def test_extract_prompt_building(self, extractor):
        # Проверяем, что _build_prompt вызывается с переданным текстом
        text = "Test vacancy description"
        with patch.object(extractor, '_build_prompt', wraps=extractor._build_prompt) as mock_build:
            extractor._call_api.return_value = "Skill1"
            extractor.extract(text)
            mock_build.assert_called_once_with(text)
            