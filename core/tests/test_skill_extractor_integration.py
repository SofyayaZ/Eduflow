import pytest
import vcr
import os
from dotenv import load_dotenv
from core.services.skill_extractor import SkillExtractor

# Загружаем переменные из .env файла (находится в корне проекта)
load_dotenv()

my_vcr = vcr.VCR(
    cassette_library_dir='core/tests/fixtures/cassettes',
    record_mode='once',
    filter_headers=['Authorization']
)

@pytest.fixture
def extractor():
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set in environment variables")
    api_url = os.getenv('DEEPSEEK_API_URL')
    if not api_url:
        pytest.skip("DEEPSEEK_API_URL not set in environment variables")
    return SkillExtractor(api_key=api_key, api_url=api_url)

@my_vcr.use_cassette('extract_skills_real.yaml')
def test_extract_skills_real(extractor):
    text = "We are looking for a Python developer with experience in Django and PostgreSQL."
    skills = extractor.extract(text)
    assert isinstance(skills, list)
    assert len(skills) > 0
    assert any('python' in s.lower() for s in skills)
    assert any('django' in s.lower() for s in skills)
    assert any('postgresql' in s.lower() for s in skills)

@my_vcr.use_cassette('extract_skills_empty.yaml')
def test_extract_skills_empty_text(extractor):
    text = "Мы ищем хорошего специалиста."
    skills = extractor.extract(text)
    assert isinstance(skills, list)
    assert len(skills) == 0

@my_vcr.use_cassette('extract_skills_russian.yaml')
def test_extract_skills_russian_text(extractor):
    text = "Требуется разработчик на Python с опытом работы с Django и PostgreSQL и умением работать с Docker контейнерами."
    skills = extractor.extract(text)
    assert isinstance(skills, list)
    assert len(skills) > 0
    assert any('python' in s.lower() for s in skills)
    assert any('django' in s.lower() for s in skills)
    assert any('postgresql' in s.lower() for s in skills)
    assert any('docker' in s.lower() for s in skills)
