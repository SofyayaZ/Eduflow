import pytest
import vcr
import os
from dotenv import load_dotenv
from core.services.skill_normalizer import SkillNormalizer
from core.models import Skill

# Загружаем переменные из .env
load_dotenv()

my_vcr = vcr.VCR(
    cassette_library_dir='core/tests/fixtures/cassettes',
    record_mode='once',
    filter_headers=['Authorization']
)

@pytest.fixture
def normalizer():
    """Фикстура для реального SkillNormalizer (с реальным API)."""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in environment variables")
    api_url = os.getenv('DEEPSEEK_API_URL')
    if not api_url:
        pytest.skip("DEEPSEEK_API_URL not set in environment variables")
    return SkillNormalizer(api_url=api_url, api_key=api_key)


@pytest.mark.django_db
class TestSkillNormalizerIntegration:
    
    @my_vcr.use_cassette('normalize_kubernetes.yaml')
    def test_normalize_kubernetes(self, normalizer):
        """Нормализация навыка, отсутствующего в canonical_map (Kubernetes)."""
        raw = "kubernetes"
        normalized = normalizer.normalize(raw)
        assert isinstance(normalized, str)
        assert normalized != ""
        # Ожидаем, что LLM вернёт что-то вроде "Kubernetes"
        assert normalized.lower() == "kubernetes"  # или с большой буквы
    
    @my_vcr.use_cassette('normalize_unknown_with_typo.yaml')
    def test_normalize_typo(self, normalizer):
        """Нормализация названия с опечаткой."""
        raw = "djanggo"
        normalized = normalizer.normalize(raw)
        assert isinstance(normalized, str)
        # LLM должна исправить на "Django"
        assert normalized.lower() == "django"
    
    @my_vcr.use_cassette('normalize_phrase.yaml')
    def test_normalize_phrase(self, normalizer):
        """Нормализация фразы (должна вернуть одно каноническое название)."""
        raw = "object relational mapping"
        normalized = normalizer.normalize(raw)
        # Ожидаем, что LLM выделит "ORM" или "SQLAlchemy"
        assert isinstance(normalized, str)
        assert len(normalized) > 0
    
    @my_vcr.use_cassette('normalize_already_canonical.yaml')
    def test_normalize_already_canonical_not_in_map(self, normalizer):
        """Нормализация уже канонического названия, но не входящего в map."""
        raw = "Celery"
        # В canonical_map нет 'celery' (по крайней мере в предоставленном коде)
        normalized = normalizer.normalize(raw)
        assert normalized == "Celery"  # LLM должна вернуть то же самое
    
    @my_vcr.use_cassette('create_skill_from_normalization.yaml')
    def test_get_or_create_skill_new(self, normalizer):
        """Создание нового навыка в БД после нормализации через LLM."""
        # Используем название, которого нет в canonical_map и в БД
        raw = "FastAPI framework"
        # Убедимся, что навыка ещё нет
        assert not Skill.objects.filter(name__iexact="FastAPI").exists()
        
        skill = normalizer.get_or_create_skill(raw)
        assert skill is not None
        assert skill.name == "FastAPI"  # LLM должна нормализовать до "FastAPI"
        assert skill.skill_type == Skill.SkillType.TOOL  # классификатор определит как инструмент
        
        # Проверяем, что навык сохранился в БД
        assert Skill.objects.filter(name="FastAPI").exists()
    
    @my_vcr.use_cassette('create_skill_existing.yaml')
    def test_get_or_create_skill_existing(self, normalizer):
        """Получение существующего навыка (без создания нового)."""
        # Сначала создаём навык напрямую
        existing = Skill.objects.create(name="Docker", skill_type=Skill.SkillType.TOOL)
        
        # Теперь вызываем нормализатор с raw-названием, которое должно нормализоваться в "Docker"
        raw = "docker"
        skill = normalizer.get_or_create_skill(raw)
        assert skill == existing
        assert skill.name == "Docker"
    
    @my_vcr.use_cassette('normalize_empty.yaml')
    def test_normalize_empty(self, normalizer):
        """Пустая строка не должна вызывать API."""
        result = normalizer.normalize("")
        assert result == ""
        result = normalizer.normalize("   ")
        assert result == ""
    
    @my_vcr.use_cassette('normalize_from_cache.yaml')
    def test_normalize_caching(self, normalizer):
        """Проверяем, что результат нормализации кэшируется (интеграционно)."""
        from django.core.cache import cache
        raw = "pytest"
        cache_key = f"skill_norm:{raw.lower()}"
        # Очищаем кэш перед тестом
        cache.delete(cache_key)
        
        # Первый вызов – должен идти в LLM
        normalized1 = normalizer.normalize(raw)
        assert cache.get(cache_key) == normalized1
        
        # Второй вызов – должен взять из кэша
        # Подменяем _call_api, чтобы он упал, если будет вызван
        original_call = normalizer._call_api
        normalizer._call_api = lambda x: (1/0)  # вызовет ошибку
        normalized2 = normalizer.normalize(raw)
        assert normalized2 == normalized1
        normalizer._call_api = original_call
