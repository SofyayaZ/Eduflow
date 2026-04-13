import pytest
from unittest.mock import patch, Mock
from requests.exceptions import ConnectionError, HTTPError
from core.services.skill_extractor import SkillExtractor


@pytest.fixture
def skill_extractor():
    return SkillExtractor(api_key="fake", api_url="https://fake.api")


@patch('core.services.skill_extractor.requests.post')
def test_extract_success(mock_post, skill_extractor):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'choices': [{'message': {'content': 'Python, Django, PostgreSQL'}}]
    }
    mock_post.return_value = mock_response
    skills = skill_extractor.extract("We need Python and Django")
    assert skills == ['Python', 'Django', 'PostgreSQL']
    mock_post.assert_called_once()


@patch('core.services.skill_extractor.requests.post')
def test_extract_empty_text(mock_post, skill_extractor):
    skills = skill_extractor.extract("")
    assert skills == []
    mock_post.assert_not_called()


@patch('core.services.skill_extractor.requests.post')
def test_extract_network_error(mock_post, skill_extractor):
    mock_post.side_effect = ConnectionError("No connection")
    skills = skill_extractor.extract("Some text")
    assert skills == []
    assert mock_post.call_count == 3


@patch('core.services.skill_extractor.requests.post')
def test_extract_http_error(mock_post, skill_extractor):
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = HTTPError("HTTP 500")
    mock_post.return_value = mock_response
    skills = skill_extractor.extract("Some text")
    assert skills == []
    assert mock_post.call_count == 3