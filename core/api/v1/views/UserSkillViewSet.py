from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from core.api.v1.serializers import UserSkillSerializer
from core.models import UserSkill


class UserSkillViewSet(viewsets.ModelViewSet):
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]

    # Возврат навыков текущего пользователя
    def get_queryset(self):
        return UserSkill.objects.filter(user=self.request.user)
    
    # Создание навыков с автоматическим привязыванием к пользователю
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        