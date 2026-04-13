import pytest
import requests
from unittest.mock import patch, Mock
from core.repository import SkillRepository
from core.services.skill_normalizer import SkillNormalizer


@pytest.fixture
def skill_normalizer():
    return SkillNormalizer(api_key="fake", api_url="https://fake.api")

# Нормализация навыка по словарю
@patch('core.services.skill_normalizer.requests.post')
def test_normalize_from_canonical_map(mock_post, skill_normalizer):
    """Навык, присутствующий в canonical_map, не вызывает API."""
    normalized = skill_normalizer.normalize("python3")
    assert normalized == "Python"
    mock_post.assert_not_called()  # API не вызывался

# Нормализация навыка по запросу к API
from django.core.cache import cache
@patch('core.services.skill_normalizer.requests.post')
def test_normalize_success_api_call(mock_post, skill_normalizer):
    cache.clear()  # очищаем кэш
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'choices': [{'message': {'content': '"Kubernetes"'}}]
    }
    mock_post.return_value = mock_response
    normalized = skill_normalizer.normalize("k8s")
    assert normalized == "Kubernetes"
    mock_post.assert_called_once()

# Нормализация при пустой строке - должна вернуть пустую строку без вызова API
@patch('core.services.skill_normalizer.requests.post')
def test_normalize_empty_input(mock_post, skill_normalizer):
    result = skill_normalizer.normalize("")
    assert result == ""
    mock_post.assert_not_called()

# Нормализация при сетевой ошибке - должна вернуть исходное название с первой буквой заглавной
@patch('core.services.skill_normalizer.requests.post')
def test_normalize_network_error(mock_port, skill_normalizer):
    mock_port.side_effect = requests.RequestException("No connection")
    result = skill_normalizer.normalize("java")
    assert result == "Java"
    assert mock_port.call_count == 3

# Нормализация с лишними символами - кавычки и точка должны быть удалены
@patch('core.services.skill_normalizer.requests.post')
def test_normalizer_with_extra_characters(mock_post, skill_normalizer):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'choices': [{'message': {'content': '"Django."'}}]}
    mock_post.return_value = mock_response
    normalized = skill_normalizer.normalize("django")
    assert normalized == "Django"

# Проверка записи в БД
@pytest.mark.django_db
@patch('core.services.skill_normalizer.SkillRepository.get_or_create')
def test_normalize_and_save_to_db(mock_repo_get_or_create, skill_normalizer):
    with patch.object(skill_normalizer, 'normalize', return_value="PostgreSQL") as mock_normalize:
        mock_repo_get_or_create.return_value = (Mock(name="skill"), True)
        skill = skill_normalizer.get_or_create_skill("postgres")
        assert skill is not None
        mock_normalize.assert_called_once_with("postgres")
        mock_repo_get_or_create.assert_called_once_with(name="PostgreSQL")
