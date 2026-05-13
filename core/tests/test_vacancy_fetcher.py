import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

import requests
from tenacity import RetryError
from core.services.vacancy_fetcher import VacancyFetcher
from core.models import JobTarget


@pytest.fixture
def mock_job_targets(db):
    """Создаём активные цели в БД (для тестов, где нужно реальное БД)."""
    JobTarget.objects.create(name="Python Developer", is_active=True)
    JobTarget.objects.create(name="Data Scientist", is_active=True)
    JobTarget.objects.create(name="Inactive", is_active=False)
    return ["Python Developer", "Data Scientist"]


@pytest.fixture
def fetcher():
    """Создаёт экземпляр VacancyFetcher с замоканными внешними зависимостями."""
    with patch('core.services.vacancy_fetcher.VacancyRepository'), \
         patch('core.services.vacancy_fetcher.VacancySkillRepository'), \
         patch('core.services.vacancy_fetcher.SkillNormalizer'), \
         patch('core.services.vacancy_fetcher.SkillExtractor'), \
         patch('core.services.vacancy_fetcher.PrerequisiteExtractor'), \
         patch('core.services.vacancy_fetcher.requests'), \
         patch('core.services.vacancy_fetcher.cache'), \
         patch('core.models.Vacancy.objects.filter'):   # добавили мок для Vacancy.objects.filter
        fetcher = VacancyFetcher(region_code="77")
        # Мокаем метод, чтобы он не обращался к реальной БД
        fetcher._get_active_job_titles = Mock(return_value=["Python Developer", "Data Scientist"])
        return fetcher


@pytest.fixture
def fetcher_with_targets(db):
    """Создаёт активные JobTarget и возвращает VacancyFetcher (с реальной БД для JobTarget)."""
    JobTarget.objects.create(name="Python Developer", is_active=True)
    JobTarget.objects.create(name="Data Scientist", is_active=True)
    # Не мокаем _get_active_job_titles, чтобы он реально читал из БД
    return VacancyFetcher(region_code="77")


@pytest.mark.django_db
class TestVacancyFetcher:
    # -------------------- _get_active_job_titles --------------------
    def test_get_active_job_titles(self, mock_job_targets):
        """Проверяем, что возвращаются только активные цели."""
        titles = VacancyFetcher._get_active_job_titles()
        assert set(titles) == {"Python Developer", "Data Scientist"}

    # -------------------- _build_params --------------------
    def test_build_params_with_region(self):
        fetcher = VacancyFetcher(region_code="77")
        params = fetcher._build_params(page=2, job_title="Python")
        assert params == {
            'text': 'Python',
            'limit': 10,
            'offset': 20,
            'region': '77'
        }

    def test_build_params_without_region(self):
        fetcher = VacancyFetcher(region_code=None)
        params = fetcher._build_params(page=0, job_title="Analyst")
        assert params == {
            'text': 'Analyst',
            'limit': 10,
            'offset': 0
        }

    # -------------------- _fetch_page --------------------
    @patch('core.services.vacancy_fetcher.requests.get')
    def test_fetch_page_success(self, mock_get, fetcher):
        mock_response = Mock()
        mock_response.json.return_value = {"results": {"vacancies": []}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetcher._fetch_page("Python", 1)
        assert result == {"results": {"vacancies": []}}
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs['params']['text'] == 'Python'
        assert kwargs['params']['limit'] == 10
        assert kwargs['params']['offset'] == 10
        assert kwargs['headers']['User-Agent'] == 'EduFlow/1.0 (contact@eduflow.ru)'

    @patch('core.services.vacancy_fetcher.requests.get')
    def test_fetch_page_http_error(self, mock_get, fetcher):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        with pytest.raises(RetryError):
            fetcher._fetch_page("Python", 0)

    # -------------------- _fetch_all_for_job_title --------------------
    @patch.object(VacancyFetcher, '_fetch_page')
    def test_fetch_all_pages(self, mock_fetch_page, fetcher_with_targets):
        # Разрешаем загрузку до 3 страниц 
        fetcher_with_targets.MAX_PAGES = 3
        # Первая страница – 10 вакансий (PER_PAGE)
        # Вторая – 10 вакансий
        # Третья – пустая
        mock_fetch_page.side_effect = [
            {"results": {"vacancies": [{"id": str(i)} for i in range(10)]}},
            {"results": {"vacancies": [{"id": str(i)} for i in range(10)]}},
            {"results": {"vacancies": []}}
        ]
        result = fetcher_with_targets._fetch_all_for_job_title("Python")
        assert len(result) == 20
        assert mock_fetch_page.call_count == 3

    @patch.object(VacancyFetcher, '_fetch_page')
    def test_fetch_all_max_pages(self, mock_fetch_page, fetcher):
        fetcher.MAX_PAGES = 2
        mock_fetch_page.return_value = {"results": {"vacancies": [{"id": f"id{i}"} for i in range(10)]}}
        result = fetcher._fetch_all_for_job_title("Python")
        assert len(result) == 20
        assert mock_fetch_page.call_count == 2

    @patch.object(VacancyFetcher, '_fetch_page')
    def test_fetch_page_exception_break(self, mock_fetch_page, fetcher):
        mock_fetch_page.side_effect = Exception("API error")
        result = fetcher._fetch_all_for_job_title("Python")
        assert result == []
        mock_fetch_page.assert_called_once()

    # -------------------- _parse_date --------------------
    def test_parse_date_valid(self):
        date_str = "2025-04-28T10:30:00+03:00"
        dt = VacancyFetcher._parse_date(date_str)
        assert dt == datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        assert dt.tzinfo is not None

    def test_parse_date_utc_z(self):
        date_str = "2025-04-28T10:30:00Z"
        dt = VacancyFetcher._parse_date(date_str)
        assert dt == datetime.fromisoformat('2025-04-28T10:30:00+00:00')

    def test_parse_date_invalid(self):
        dt = VacancyFetcher._parse_date("invalid")
        now = datetime.now(timezone.utc)
        assert (now - dt).total_seconds() < 1

    def test_parse_date_empty(self):
        dt = VacancyFetcher._parse_date("")
        now = datetime.now(timezone.utc)
        assert (now - dt).total_seconds() < 1

    # -------------------- fetch_and_save --------------------
    @patch.object(VacancyFetcher, '_fetch_all_for_job_title')
    def test_fetch_and_save_no_job_titles(self, mock_fetch_all):
        fetcher = VacancyFetcher()
        fetcher._get_active_job_titles = Mock(return_value=[])
        result = fetcher.fetch_and_save()
        assert result == 0
        mock_fetch_all.assert_not_called()

    @patch.object(VacancyFetcher, '_fetch_all_for_job_title')
    def test_fetch_and_save_no_vacancies(self, mock_fetch_all, fetcher):
        mock_fetch_all.return_value = []
        result = fetcher.fetch_and_save()
        assert result == 0

    @patch('core.services.vacancy_fetcher.VacancyRepository')
    @patch('core.services.vacancy_fetcher.VacancySkillRepository')
    @patch('core.services.vacancy_fetcher.SkillExtractor')
    @patch('core.services.vacancy_fetcher.SkillNormalizer')
    @patch('core.services.vacancy_fetcher.PrerequisiteExtractor')
    @patch.object(VacancyFetcher, '_fetch_all_for_job_title')
    @patch('core.models.Vacancy.objects.filter')
    def test_fetch_and_save_new_vacancies(
        self, mock_vacancy_filter, mock_fetch_all, mock_prereq, mock_normalizer,
        mock_extractor, mock_vacancy_skill_repo, mock_vacancy_repo, fetcher
    ):
        # Исправление: подменяем список активных должностей
        fetcher._get_active_job_titles = Mock(return_value=["Python Developer"])
        
        with patch('core.models.JobTarget.objects.filter') as mock_job_target_filter:
            mock_job_target = Mock(id=1, name="Python Developer")
            mock_job_target_filter.return_value.first.return_value = mock_job_target

            raw_vacancies = [
                {
                    "vacancy": {
                        "id": "v1",
                        "job-name": "Python Dev",
                        "company": {"name": "Tech"},
                        "region": {"name": "Moscow"},
                        "publication-date": "2025-04-28T10:00:00+03:00",
                        "duty": "Нужны Python и Django"
                    }
                },
                {
                    "vacancy": {
                        "id": "v2",
                        "job-name": "Data Scientist",
                        "company": {"name": "DataCorp"},
                        "region": {"name": "SPB"},
                        "publication-date": "2025-04-27T00:00:00Z",
                        "duty": "Требуется Python, SQL, ML"
                    }
                }
            ]
            mock_fetch_all.return_value = raw_vacancies

            mock_queryset = Mock()
            mock_queryset.exists.return_value = False
            mock_vacancy_filter.return_value = mock_queryset

            mock_vacancy_repo.get_or_create.side_effect = lambda **kwargs: (Mock(id=kwargs['id_vacancy']), True)

            mock_extractor_instance = Mock()
            mock_extractor_instance.extract.return_value = ["Python", "Django"]
            mock_extractor.return_value = mock_extractor_instance

            mock_normalizer_instance = Mock()
            mock_skill = Mock()
            mock_skill.name = "Python"
            mock_normalizer_instance.get_or_create_skill.return_value = mock_skill
            mock_normalizer.return_value = mock_normalizer_instance

            mock_prereq_instance = Mock()
            mock_prereq_instance.extract_and_save_prerequisites.return_value = 2
            mock_prereq.return_value = mock_prereq_instance

            result = fetcher.fetch_and_save()
            assert result == 2
            assert mock_vacancy_repo.get_or_create.call_count == 2
            mock_extractor_instance.extract.assert_called()
            mock_normalizer_instance.get_or_create_skill.assert_called()
            mock_vacancy_skill_repo.get_or_create.assert_called()
            mock_prereq_instance.extract_and_save_prerequisites.assert_called()

    @patch('core.services.vacancy_fetcher.VacancyRepository')
    @patch.object(VacancyFetcher, '_fetch_all_for_job_title')
    @patch('core.models.Vacancy.objects.filter')
    def test_fetch_and_save_skip_existing(
        self, mock_vacancy_filter, mock_fetch_all, mock_vacancy_repo, fetcher_with_targets
    ):
        # Мокаем JobTarget.objects.filter
        with patch('core.models.JobTarget.objects.filter') as mock_job_target_filter:
            mock_job_target = Mock(id=1, name="Python Developer")
            mock_job_target_filter.return_value.first.return_value = mock_job_target

            raw_vacancies = [{"vacancy": {"id": "v1", "job-name": "Dev", "duty": "desc"}}]
            mock_fetch_all.return_value = raw_vacancies

            # Вакансия уже существует
            mock_queryset = Mock()
            mock_queryset.exists.return_value = True
            mock_vacancy_filter.return_value = mock_queryset

            result = fetcher_with_targets.fetch_and_save()
            assert result == 0
            mock_vacancy_repo.get_or_create.assert_not_called()

    @patch('core.services.vacancy_fetcher.VacancyRepository')
    @patch('core.services.vacancy_fetcher.VacancySkillRepository')
    @patch.object(VacancyFetcher, '_fetch_all_for_job_title')
    @patch('core.models.Vacancy.objects.filter')
    def test_fetch_and_save_empty_description(
        self, mock_vacancy_filter, mock_fetch_all, mock_vacancy_skill_repo, mock_vacancy_repo, fetcher
    ):
        # Подменяем активные должности
        fetcher._get_active_job_titles = Mock(return_value=["Python Developer"])
        
        # Мокаем JobTarget.objects.filter
        with patch('core.models.JobTarget.objects.filter') as mock_job_target_filter:
            mock_job_target = Mock(id=1, name="Python Developer")
            mock_job_target_filter.return_value.first.return_value = mock_job_target

            raw_vacancies = [{"vacancy": {"id": "v1", "job-name": "Dev", "duty": ""}}]
            mock_fetch_all.return_value = raw_vacancies

            mock_queryset = Mock()
            mock_queryset.exists.return_value = False
            mock_vacancy_filter.return_value = mock_queryset

            mock_vacancy_repo.get_or_create.return_value = (Mock(id="v1", description=""), True)

            result = fetcher.fetch_and_save()
            assert result == 1
            mock_vacancy_skill_repo.get_or_create.assert_not_called()
        