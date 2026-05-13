import logging

from rest_framework import viewsets, status
from rest_framework.decorators import APIView, action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.core.cache import cache

from core.models import JobTarget
from core.services.vacancy_fetcher import VacancyFetcher
from core.tasks.fetch_tasks import fetch_vacancies
from core.api.v1.serializers import JobTargetAdminSerializer, FetchVacanciesSerializer


logger = logging.getLogger(__name__)

class AdminJobTargetViewSet(viewsets.ModelViewSet):
    """
    Управление целями сбора вакансий (только для администраторов).
    Доступ: /api/v1/admin/job-targets/
    """
    permission_classes = [IsAdminUser]
    serializer_class = JobTargetAdminSerializer
    queryset = JobTarget.objects.all()

    @action(detail=False, methods=['post'], url_path='activate-all')
    def activate_all(self, request):
        """Активировать все цели."""
        JobTarget.objects.all().update(is_active=True)
        return Response({'status': 'all activated'})

    @action(detail=False, methods=['post'], url_path='deactivate-all')
    def deactivate_all(self, request):
        """Деактивировать все цели."""
        JobTarget.objects.all().update(is_active=False)
        return Response({'status': 'all deactivated'})


class FetchVacanciesAdminView(APIView):
    """
    Ручной запуск сбора вакансий (только для администраторов).
    POST /api/v1/admin/fetch-vacancies/
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = FetchVacanciesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        job_target_ids = data.get('job_target_ids')
        region_code = data.get('region_code')
        async_mode = data.get('async_mode', False)

        # Определяем, какие цели использовать
        if job_target_ids:
            targets = JobTarget.objects.filter(id__in=job_target_ids, is_active=True)
        else:
            targets = JobTarget.objects.filter(is_active=True)

        if not targets.exists():
            return Response({'error': 'Нет активных целей для сбора'}, status=status.HTTP_400_BAD_REQUEST)

        # Сохраняем список названий (или ID) для передачи в фетчер
        job_titles = list(targets.values_list('name', flat=True))

        if async_mode:
            # Асинхронный запуск через Celery
            task = fetch_vacancies.delay(job_titles=job_titles, region_code=region_code)
            return Response({
                'task_id': task.id,
                'status': 'started',
                'message': 'Сбор вакансий запущен в фоне. Используйте task_id для отслеживания.'
            }, status=status.HTTP_202_ACCEPTED)
        else:
            # Синхронный запуск (может выполняться долго!)
            try:
                fetcher = VacancyFetcher(job_titles=job_titles, region_code=region_code)
                saved_count = fetcher.fetch_and_save()      
                fetcher = VacancyFetcher(region_code=region_code)
                return Response({
                    'saved_count': saved_count,
                    'message': f'Сбор завершён. Сохранено вакансий: {saved_count}'
                })
            except Exception as e:
                logger.exception("Ошибка при синхронном сборе вакансий")
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)