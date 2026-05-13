from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r'job-targets', views.JobTargetViewSet, basename='job-target')
router.register(r'user-targets', views.UserTargetViewSet, basename='user-target')
router.register(r'user-skills', views.UserSkillViewSet, basename='user-skill')
router.register(r'skills', views.SkillViewSet, basename='skill')
# для админа
router.register(r'admin/job-targets', views.AdminJobTargetViewSet, basename='admin-job-targets')

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name = 'token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name = 'token_refresh'),

    path('register/', views.RegisterView.as_view(), name = 'register'),

    path('profile/', views.ProfileView.as_view(), name = 'profile'),

    path('generate-path/', views.GeneratePathView.as_view(), name = 'generate-path'),
    path('path-history/', views.PathHistoryView.as_view(), name = 'path-history'),

    # пути для админа
    path('admin/fetch-vacancies/', views.FetchVacanciesAdminView.as_view(), name='admin-fetch-vacancies'),
    path('admin/', include(router.urls)),

    path('', include(router.urls)),
]
