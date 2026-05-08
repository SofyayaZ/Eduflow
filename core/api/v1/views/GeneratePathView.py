from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView, Response
from rest_framework.permissions import IsAuthenticated
from core.models import UserTarget
from core.repository import UserSkillRepository
from core.services.path_builder import PathBuilder
from core.services.skill_matching import SkillMatchingService


class GeneratePathView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    http_method_names = ['post']

    def post(self, request):
        target_id = request.data.get('job_target_id')
        if not target_id:
            return Response({'error': 'job_target_id is required'}, status=400)
        try:
            target = UserTarget.objects.get(id=target_id, user=request.user)
        except UserTarget.DoesNotExist:
            return Response({'error': 'User target not found'}, status=404)

        region = request.user.preferred_region if request.user.preferred_region else None

        # Проверка наличия вакансий
        if not SkillMatchingService.has_vacancies_for_target(target.target_job.name, region=region):
            if region:
                message = f'По вашему региону "{region}" вакансий для выбранной цели не найдено. Попробуйте сменить регион в профиле.'
            else:
                message = 'Вакансий для выбранной цели не найдено. Возможно, стоит добавить регион в профиль.'
            return Response({'message': message}, status=200)

        # 1. Все недостающие навыки с частотами
        missing_skills = SkillMatchingService.get_missing_skills(request.user, target.target_job.name)
        if not missing_skills:
            return Response({'message': 'Отсутствующих навыков не найдено'}, status=200)

        # 2. Навыки пользователя
        user_skills = set(UserSkillRepository.get_skills_for_user(request.user).values_list('skill_id', flat=True))

        # 3. Словарь важности (skill.id -> частота)
        importance = {skill.id: freq for skill, freq in missing_skills}

        # 4. Список всех недостающих навыков (без частот)
        all_missing = [skill for skill, _ in missing_skills]

        # 5. Расширяем весь список пререквизитами (добавляем то, чего не хватает)
        expanded_skills = PathBuilder._expand_missing_with_prerequisites(all_missing, user_skills)

        graph = PathBuilder.build_graph(expanded_skills, user_skills, importance)\
        
        return Response({
            'missing_skills': [{'id': s.id, 'name': s.name} for s in expanded_skills],
            'graph': graph
        })
    