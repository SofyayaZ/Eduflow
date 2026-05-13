from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import JobTarget
from core.services.vacancy_fetcher import VacancyFetcher
import logging


logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fetch vacancies from external API (trudvsem) for active job targets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job-titles',
            nargs='+',
            type=str,
            help='List of job titles to fetch (overrides active JobTargets)'
        )
        parser.add_argument(
            '--region-code',
            type=str,
            help='Region code (e.g., "77" for Moscow)'
        )

    def handle(self, *args, **options):
        job_titles = options.get('job_titles')
        region_code = options.get('region_code')

        if job_titles is None:
            job_titles = list(JobTarget.objects.filter(is_active=True).values_list('name', flat=True))
            if not job_titles:
                self.stdout.write(self.style.ERROR('No active JobTargets found and no job titles provided.'))
                return

        if region_code is None:
            region_code = getattr(settings, 'DEFAULT_REGION_CODE', None)

        self.stdout.write(f"Fetching vacancies for: {', '.join(job_titles)}")
        self.stdout.write(f"Region code: {region_code or 'all'}")

        try:
            fetcher = VacancyFetcher(job_titles=job_titles, region_code=region_code)
            saved_count = fetcher.fetch_and_save()
            self.stdout.write(self.style.SUCCESS(f'Successfully saved {saved_count} new vacancies'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch vacancies: {e}'))
            raise
        