from rest_framework.views import APIView, Response
from rest_framework.permissions import IsAuthenticated
from core.models import UserTarget
from core.repository import UserSkillRepository
from core.services.path_builder import PathBuilder
from core.services.skill_matching import SkillMatchingService
from core.services.ranking_service import RankingService


class GeneratePathView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        target_id = request.data.get('job_target_id')
        if not target_id:
            return Response({'error': 'job_target_id is required'}, status=400) 
        try:
            target = UserTarget.objects.get(id=target_id, user = request.user)
        except UserTarget.DoesNotExist:
            return Response({'error': 'User target not found'}, status=404)

        if not SkillMatchingService.has_vacancies_for_target(target.target_job.name):
            return Response({'message': 'No vacancies found for this job target'}, status=200)

        missing_skills = SkillMatchingService.get_missing_skills(request.user, target.target_job.name)
        if not missing_skills:
            return Response({'message': 'No missing skills found'}, status=200)
        
        ranked_skills = RankingService.rank_skills_by_importance(missing_skills)
        user_skills = set(UserSkillRepository.get_skills_for_user(request.user).values_list('skill_id', flat=True))

        try:
            skills_sequence = PathBuilder.build_sequence(ranked_skills, user_skills)
        except ValueError as e:
            return Response({'error': str(e)}, status=500)
        
        PathBuilder.create_path(request.user, target, skills_sequence)
        
        return Response({
            'missing_skills': [{'id' : skill.id, 'name': skill.name} for skill in ranked_skills],
            'path': [{'order': i+1, 'skill': skill.name} for i, skill in enumerate(skills_sequence, start=1)]
            })
