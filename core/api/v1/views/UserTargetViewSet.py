from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework import viewsets
from core.api.v1.serializers import UserTargetSerializer
from core.models import UserTarget


class UserTargetViewSet(viewsets.ModelViewSet):
    serializer_class = UserTargetSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return UserTarget.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
