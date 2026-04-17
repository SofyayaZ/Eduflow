import pytest
from unittest.mock import patch, Mock
from core.services.prerequisite_extractor import PrerequisiteExtractor
from django.core.cache import cache


@pytest.fixture
def prerequisite_extractor():
    with patch('core.services.prerequisite_extractor.settings') as mock_settings:
        mock_settings.DEEPSEEK_API_URL = 'https://test.api'
        mock_settings.DEEPSEEK_API_KEY = 'test-key'
        return PrerequisiteExtractor()


@pytest.fixture(autouse=True)
def clear_cache():
    """Автоматически очищает кэш перед каждым тестом."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestPrerequisiteExtractor:

    def test_init_success(self):
        with patch('core.services.prerequisite_extractor.settings') as mock_settings:
            mock_settings.DEEPSEEK_API_URL = 'https://test.api'
            mock_settings.DEEPSEEK_API_KEY = 'test-key'
            extractor = PrerequisiteExtractor()
            assert extractor.api_url == 'https://test.api'
            assert extractor.api_key == 'test-key'
            assert 'Django' in str(extractor.prerequisite_map)

    def test_is_prerequisite_same_skill(self, prerequisite_extractor, skill_python):
        assert prerequisite_extractor._is_prerequisite(skill_python, skill_python) is False

    def test_is_prerequisite_map(self, prerequisite_extractor, skill_django, skill_python):
        assert prerequisite_extractor._is_prerequisite(skill_django, skill_python) is True

    def test_is_prerequisite_reverse_map(self, prerequisite_extractor, skill_django, skill_python):
        assert prerequisite_extractor._is_prerequisite(skill_python, skill_django) is False

    def test_is_prerequisite_using_cache(self, prerequisite_extractor, skill_pandas, skill_python):
        cache_key = 'prereq:Python:skill:Pandas'
        cache.set(cache_key, True, 60)
        with patch.object(prerequisite_extractor, '_call_api') as mock_call_api:
            assert prerequisite_extractor._is_prerequisite(skill_pandas, skill_python) is True
            mock_call_api.assert_not_called()
        cache.delete(cache_key)

    def test_is_prerequisite_using_llm_no(self, prerequisite_extractor):
        # Создаём уникальные навыки, чтобы избежать кэша
        from core.models import Skill
        skill_a = Skill.objects.create(name='SkillA_unique')
        skill_b = Skill.objects.create(name='SkillB_unique')
        with patch.object(prerequisite_extractor, '_call_api', return_value='нет') as mock_call_api:
            result = prerequisite_extractor._is_prerequisite(skill_a, skill_b)
            assert result is False
            mock_call_api.assert_called_once()
        cache_key = f'prereq:{skill_b.name}:skill:{skill_a.name}'
        assert cache.get(cache_key) is False
        cache.delete(cache_key)

    def test_is_prerequisite_using_llm_yes(self, prerequisite_extractor):
        from core.models import Skill
        skill_a = Skill.objects.create(name='SkillX_unique')
        skill_b = Skill.objects.create(name='SkillY_unique')
        with patch.object(prerequisite_extractor, '_call_api', return_value='да') as mock_call_api:
            result = prerequisite_extractor._is_prerequisite(skill_a, skill_b)
            assert result is True
            mock_call_api.assert_called_once()
        cache_key = f'prereq:{skill_b.name}:skill:{skill_a.name}'
        assert cache.get(cache_key) is True
        cache.delete(cache_key)
