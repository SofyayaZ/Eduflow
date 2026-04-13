from rest_framework import viewsets, permissions
from core.models import Skill
from core.api.v1.serializers import SkillSerializer

class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Эндпоинт для получения списка доступных навыков
    """
    queryset = Skill.objects.all().order_by('name')
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated]
    