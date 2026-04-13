from rest_framework import generics, permissions
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from core.api.v1.serializers import UserSerializer


class RegisterView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer

    def post(self, request, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "preferred_region": user.preferred_region 
        }, status=201)
