from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from core.api.v1.serializers import JobTargetSerializer
from core.models import JobTarget


class JobTargetViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobTarget.objects.filter(is_active=True)
    serializer_class = JobTargetSerializer
    permission_classes = [IsAuthenticated]
