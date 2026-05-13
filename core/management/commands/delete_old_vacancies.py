from django.core.management.base import BaseCommand
from core.repository import VacancyRepository


class Command(BaseCommand):
    help = 'Deletes vacancies older than 180 days'

    def handle(self, *args, **options):
        deleted = VacancyRepository.delete_old_vacancies()
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {deleted} old vacancies')
        )
        