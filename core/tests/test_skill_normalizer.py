import pytest
from unittest.mock import Mock, patch
from django.core.cache import cache
from core.services.skill_normalizer import SkillNormalizer
from core.models import Skill


@pytest.fixture
def normalizer():
    """Создаёт экземпляр SkillNormalizer с мокнутыми API и кэшем."""
    with patch('core.services.skill_normalizer.cache') as mock_cache, \
         patch('core.services.skill_normalizer.SkillRepository') as mock_repo, \
         patch('core.services.skill_normalizer.SkillTypeClassifier') as mock_classifier:
        mock_cache.get.return_value = None
        mock_cache.set.return_value = None
        # Настройка мока классификатора
        classifier_instance = Mock()
        classifier_instance.classify_without_db.return_value = Skill.SkillType.HARD
        mock_classifier.return_value = classifier_instance
        
        # Настройка репозитория
        mock_repo.get_or_create.return_value = (Skill(name="Python"), True)
        
        # Используем реальные настройки или мок
        with patch('core.services.skill_normalizer.settings.DEEPSEEK_API_URL', 'https://fake.api'), \
             patch('core.services.skill_normalizer.settings.DEEPSEEK_API_KEY', 'fake_key'):
            normalizer = SkillNormalizer()
            # Заменяем моками внутренние зависимости
            normalizer._call_api = Mock()
            normalizer.type_classifier = classifier_instance
            return normalizer


@pytest.mark.django_db
class TestSkillNormalizer:
    def test_normalize_empty(self, normalizer):
        assert normalizer.normalize("") == ""
        assert normalizer.normalize("   ") == ""

    def test_normalize_canonical_map(self, normalizer):
        # Проверяем попадание в словарь (регистронезависимо)
        assert normalizer.normalize("питон") == "Python"
        assert normalizer.normalize("Python3") == "Python"  # по ключу 'python3'
        assert normalizer.normalize("js") == "JavaScript"
        # Отсутствующий в карте идёт в кэш/LLM
        normalizer._call_api.return_value = "Java"
        assert normalizer.normalize("Java") == "Java"  # здесь нет в canonical_map, пойдёт в LLM

    def test_normalize_cache_hit(self, normalizer):
        with patch('core.services.skill_normalizer.cache.get') as mock_cache_get:
            mock_cache_get.return_value = "NormalizedPython"
            result = normalizer.normalize("py")
            assert result == "NormalizedPython"
            mock_cache_get.assert_called_once_with("skill_norm:py")
            normalizer._call_api.assert_not_called()

    def test_normalize_llm_success(self, normalizer):
        normalizer._call_api.return_value = '"Django Framework"'
        with patch('core.services.skill_normalizer.cache.get', return_value=None), \
            patch('core.services.skill_normalizer.cache.set') as mock_cache_set:
            result = normalizer.normalize("djengo")  # нет в canonical_map
            assert result == "Django Framework"
            normalizer._call_api.assert_called_once()
            mock_cache_set.assert_called_once()

    def test_normalize_llm_failure_fallback(self, normalizer):
        normalizer._call_api.side_effect = Exception("API error")
        result = normalizer.normalize("some skill")
        # fallback: возвращаем исходное название с заглавной буквы
        assert result == "Some skill"
        normalizer._call_api.assert_called_once()

    def test_normalize_strips_quotes_and_dots(self, normalizer):
        normalizer._call_api.return_value = '"Python."'
        result = normalizer.normalize("some")
        # После удаления кавычек и точки
        assert result == "Python"

    def test_get_or_create_skill_empty(self, normalizer):
        # Мокаем normalize, чтобы вернул пустую строку
        normalizer.normalize = Mock(return_value="")
        skill = normalizer.get_or_create_skill("")
        assert skill is None

    def test_get_or_create_skill_new(self, normalizer):
        # Мокаем normalize и классификатор
        normalizer.normalize = Mock(return_value="Python")
        # Мокаем репозиторий
        mock_skill = Skill(name="Python")
        with patch('core.services.skill_normalizer.SkillRepository') as mock_repo:
            mock_repo.get_or_create.return_value = (mock_skill, True)
            skill = normalizer.get_or_create_skill("питон")
            assert skill == mock_skill
            mock_repo.get_or_create.assert_called_once_with(
                name="Python", skill_type=Skill.SkillType.HARD
            )
            # Проверяем, что классификатор вызван
            normalizer.type_classifier.classify_without_db.assert_called_once_with("Python")

    def test_get_or_create_skill_existing(self, normalizer):
        normalizer.normalize = Mock(return_value="Python")
        existing_skill = Skill(name="Python", skill_type=Skill.SkillType.HARD)
        with patch('core.services.skill_normalizer.SkillRepository') as mock_repo:
            mock_repo.get_or_create.return_value = (existing_skill, False)
            skill = normalizer.get_or_create_skill("python")
            assert skill == existing_skill
            # Классификатор не должен вызываться для существующего навыка, потому что тип уже задан
            normalizer.type_classifier.classify_without_db.assert_called_once_with("Python")
            mock_repo.get_or_create.assert_called_once()
            