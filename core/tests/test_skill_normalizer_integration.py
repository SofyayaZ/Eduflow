from dotenv import load_dotenv
import pytest
import vcr
import os
from core.services.skill_normalizer import SkillNormalizer



load_dotenv()

my_vcr = vcr.VCR(
    record_mode='once',
    cassette_library_dir='core/tests/fixtures/cassettes'
)

@pytest.fixture
def normalizer():
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        pytest.skip('Not set API key')
    api_url = os.getenv('DEEPSEEK_API_URL')
    if not api_url:
        pytest.skip('Not set API url')
    return SkillNormalizer(api_key=api_key, api_url=api_url)

@my_vcr.use_cassette('normalize_skills_python.yaml')
def test_skill_normalize_python(normalizer):
    raw_skill_name = "Питон"
    normalized_skill_name = normalizer.normalize(raw_skill_name)
    assert normalized_skill_name == "Python"

@my_vcr.use_cassette('normalize_skills_javascript.yaml')
def test_skill_normalize_javascript(normalizer):
    raw_skill_name = "js"
    normalized_skill_name = normalizer.normalize(raw_skill_name)
    assert normalized_skill_name == "JavaScript"

@pytest.mark.django_db
@my_vcr.use_cassette('get_or_create_skill.yaml')
def test_get_or_create_skill(normalizer):
    skill1 = normalizer.get_or_create_skill("postgresql")
    assert skill1 is not None
    assert skill1.name == "PostgreSQL"
    skill2 = normalizer.get_or_create_skill("postgresql")
    assert skill1.id == skill2.id
