from django.utils import timezone

from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    preferred_region = models.CharField(max_length=255, blank=True)
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='core_user_groups',
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='core_user_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    class Meta:
        db_table = 'Users'
    def __str__(self):
        return self.username


class Skill(models.Model):
    class SkillType(models.TextChoices):
        SOFT = 'soft', 'Мягкий'
        HARD = 'hard', 'Технический'
        TOOL = 'tool', 'Инструмент'

    name = models.CharField(max_length=255, unique=True)
    skill_type = models.CharField(
        max_length=10,
        choices = SkillType.choices,
        default = SkillType.HARD,
        db_index = True
    )

    class Meta:
        db_table = 'Skills'
    def __str__(self):
        return f"{self.name} ({self.get_skill_type_display()})"


class Vacancy(models.Model):
    id_vacancy = models.CharField(max_length=255, unique=True, primary_key=True)  # уникальный идентификатор вакансии
    title = models.TextField()                                                    # заголовок вакансии
    published_at = models.DateTimeField(default=timezone.now)                     # дата публикации
    company = models.CharField(max_length=255)                                    # компания-работодатель
    source = models.CharField(max_length=50)                                      # источник вакансии (например, hh.ru)
    fetched_at = models.DateTimeField(default=timezone.now)                       # дата загрузки в нашу БД
    region = models.CharField(max_length=100, blank=True, db_index=True)          # регион вакансии
    description = models.TextField(blank=True)
    job_target = models.ForeignKey('JobTarget', null=True, on_delete=models.SET_NULL)
    class Meta:
        db_table = 'Vacancies'
    def __str__(self):
        return f"{self.title} ({self.company})"


class JobTarget(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)               # можно отключить сбор вакансий
    class Meta:
        db_table = 'JobTargets'
    def __str__(self):
        return f"{self.name}"


class VacancySkill(models.Model):
    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.CASCADE,
        related_name='vacancy_skills'
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='vacancy_skills')
    class Meta:
        db_table = 'VacancySkills'
        constraints = [models.UniqueConstraint(fields=['vacancy', 'skill'], name='unique_vacancy_skill')]


class SkillPrerequisite(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='prerequisites_set')
    prerequisite_skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='required_for')
    class Meta:
        db_table = 'SkillPrerequisites'
        constraints = [
            models.UniqueConstraint(fields=['skill', 'prerequisite_skill'], name='unique_skill'),
            models.CheckConstraint(
                condition=~models.Q(skill=models.F('prerequisite_skill')),
                name='no_self_prerequisite'
            )
        ]
    def __str__(self):
        return f"{self.prerequisite_skill.name} → {self.skill.name}"
    

class UserSkill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    class Meta:
        db_table = 'UserSkills'
        constraints = [models.UniqueConstraint(fields=['user', 'skill'], name='unique_user_skill')]
    def __str__(self):
        return f"{self.user.username} - {self.skill.name}"


class UserTarget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='targets')
    target_job = models.ForeignKey(JobTarget, on_delete=models.CASCADE, related_name='users_target')
    class Meta:
        db_table = 'UserTargets'
        constraints = [models.UniqueConstraint(fields=['user', 'target_job'], name='unique_user_target')]
    def __str__(self):
        return f"{self.user.username}: {self.target_job.name}"


class GeneratedPath(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_paths')
    target = models.ForeignKey(UserTarget, on_delete=models.CASCADE, related_name='generated_paths')
    generated_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False)  # активная траектория
    class Meta:
        db_table = 'GeneratedPaths'
    def __str__(self):
        return f"Path for {self.user.username} -> {self.target.target_job.name} ({self.generated_at})"


class PathStep(models.Model):
    generated_path = models.ForeignKey(GeneratedPath, on_delete=models.CASCADE, related_name='steps')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    step_order = models.PositiveIntegerField()  # порядковый номер
    class Meta:
        db_table = 'PathSteps'
        ordering = ['step_order']  # сортировка по порядку
        constraints = [
            models.UniqueConstraint(fields=['generated_path', 'step_order'], name='unique_step_order_per_path')
        ]
    def __str__(self):
        return f"{self.generated_path}: step {self.step_order} - {self.skill.name}"
