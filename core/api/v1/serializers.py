from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models import UserSkill, JobTarget, UserTarget, GeneratedPath, PathStep, Skill

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'preferred_region', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']

class UserSkillSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    skill_id = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), source='skill', write_only=True
    )

    class Meta:
        model = UserSkill
        fields = ['id', 'skill', 'skill_id']

class JobTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobTarget
        fields = ['id', 'name', 'is_active']

class UserTargetSerializer(serializers.ModelSerializer):
    target_job = JobTargetSerializer(read_only=True)
    target_job_id = serializers.PrimaryKeyRelatedField(
        queryset=JobTarget.objects.filter(is_active=True), source='target_job', write_only=True
    )

    class Meta:
        model = UserTarget
        fields = ['id', 'target_job', 'target_job_id', 'user']
        read_only_fields = ['user']

class PathStepSerializer(serializers.ModelSerializer):
    skill = SkillSerializer()

    class Meta:
        model = PathStep
        fields = ['id', 'step_order', 'skill']

class GeneratedPathSerializer(serializers.ModelSerializer):
    steps = PathStepSerializer(many=True, read_only=True)
    target = UserTargetSerializer(read_only=True)

    class Meta:
        model = GeneratedPath
        fields = ['id', 'target', 'generated_at', 'is_current', 'steps']

# Для админа
class JobTargetAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobTarget
        fields = ['id', 'name', 'is_active']
        read_only_fields = ['id']

class FetchVacanciesSerializer(serializers.Serializer):
    job_target_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False,
        help_text="ID целей для сбора. Если не указаны – используются активные цели"
    )
    region_code = serializers.CharField(max_length=50, required=False, help_text="Код региона (например, 77 для Москвы и 47 для Питера)")
    async_mode = serializers.BooleanField(default=False, help_text="Запустить через Celery асинхронно или синхронно")
