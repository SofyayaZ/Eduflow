import pytest
import vcr
from django.core.management import call_command
from core.models import JobTarget, Vacancy, VacancySkill, Skill
from core.services.vacancy_fetcher import VacancyFetcher


my_vcr = vcr.VCR(
    cassette_library_dir='core/tests/fixtures/cassettes',
    record_mode='once',               # записываем только если кассета отсутствует
    filter_headers=['Authorization', 'User-Agent'],
    decode_compressed_response=True,
)

@pytest.fixture
def active_job_target(db):
    """Создаёт активную цель для сбора вакансий."""
    target, created = JobTarget.objects.get_or_create(
        name="C++ разработчик",
        defaults={"is_active": True}
    )
    if not created:
        target.is_active = True
        target.save()
    return target


@pytest.mark.django_db
@my_vcr.use_cassette('vacancy_fetcher_integration.yaml')
def test_vacancy_fetcher_integration(active_job_target):
    """
    Интеграционный тест сборщика вакансий с реальным API trudvsem.
    Использует VCR для записи/воспроизведения HTTP-трафика.
    """
    # Создаём сборщик с регионом Москва (код 77)
    fetcher = VacancyFetcher(region_code='77')

    # Запускаем сбор и сохранение вакансий
    saved_count = fetcher.fetch_and_save()

    # Проверяем, что хотя бы одна вакансия была сохранена
    assert saved_count > 0, "Не сохранено ни одной вакансии"

    # Проверяем, что вакансии появились в БД с правильным источником
    vacancies = Vacancy.objects.filter(source='trudvsem')
    assert vacancies.count() >= saved_count

    # Проверяем, что у некоторых вакансий есть описание (важно для извлечения навыков)
    vacancies_with_desc = vacancies.exclude(description='')
    if vacancies_with_desc.exists():
        # Проверяем, что были созданы связи VacancySkill
        vacancy_skills = VacancySkill.objects.filter(vacancy__in=vacancies_with_desc)
        # Может быть 0, если ни в одной вакансии не нашли навыков
        if vacancy_skills.exists():
            # Проверяем, что связанные навыки действительно существуют в таблице Skill
            skill_ids = vacancy_skills.values_list('skill_id', flat=True)
            skills = Skill.objects.filter(id__in=skill_ids)
            assert skills.count() == len(set(skill_ids)), "Не все навыки найдены в БД"
