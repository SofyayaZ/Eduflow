from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from core.api.v1.serializers import UserTargetSerializer
from core.repository import GeneratedPathRepository, PathStepRepository


class PathHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        paths = GeneratedPathRepository.get_history_for_user(request.user)
        data = []
        for path in paths:
            steps = PathStepRepository.get_for_path(path)
            data.append({
                'id' : path.id,
                'target' : UserTargetSerializer(path.target).data,
                'generated_at' : path.generated_at,
                'is_current' : path.is_current,
                'steps' : [{'order' : skill.step_order, 'skill' : skill.skill.name} for skill in steps]
            })
        return Response(data, status=200)
