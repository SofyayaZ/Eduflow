from django.core.management.base import BaseCommand
from core.models import Skill
from core.repository import VacancySkillRepository
from core.services.prerequisite_extractor import PrerequisiteExtractor


class Command(BaseCommand):
    def handle(self, *args, **options):
        min_freq = 2
        importance = {item['skill']: item['importance'] for item in VacancySkillRepository.get_global_skill_importance()}
        skills = Skill.objects.filter(id__in=[sid for sid, freq in importance.items() if freq >= min_freq])
        extractor = PrerequisiteExtractor()
        extractor.extract_and_save_prerequisites(skills, importance_map=importance, min_freq=min_freq)
