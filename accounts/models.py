"""
apps/accounts/models.py

Custom User model + role-based profiles for EduSync Pro.

Roles:
- ORG_ADMIN: Can approve/reject exams, manage org settings
- TEACHER: Creates and submits exams
- STUDENT: Views own published results
- PARENT: Views their children's published results
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from core.models import Organization, TimeStampedModel, ClassRoom


class User(AbstractUser):
    """
    Custom User extending Django's AbstractUser.
    Adds organization FK and role for multi-tenant RBAC.

    CRITICAL: organization field is how we scope ALL queries.
    A user belongs to exactly one organization.
    """

    class Role(models.TextChoices):
        ORG_ADMIN = 'org_admin', 'Organization Admin'
        TEACHER = 'teacher', 'Teacher'
        STUDENT = 'student', 'Student'
        PARENT = 'parent', 'Parent'
        SUPER_ADMIN = 'super_admin', 'Super Admin'  # Platform-level only

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(

        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,  # Super admins have no org
        related_name='users'
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TEACHER
    )
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # Forces password change on next login (set True for all auto-generated accounts)
    must_change_password = models.BooleanField(
        default=False,
        help_text="If True, user must change password before using the system"
    )

    # ── Role helpers ──────────────────────────────
    @property
    def is_org_admin(self):
        return self.role == self.Role.ORG_ADMIN

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_parent(self):
        return self.role == self.Role.PARENT

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


class StudentProfile(TimeStampedModel):
    """
    Extended profile for students.
    Links a User (role=student) to a ClassRoom.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='student_profiles'
    )
    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )
    admission_number = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # Future: GPA field, ranking_position, etc.

    class Meta:
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"Student: {self.user.get_full_name()}"


class TeacherProfile(TimeStampedModel):
    """
    Extended profile for teachers.
    Future: assigned subjects, assigned classrooms.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='teacher_profiles'
    )
    employee_number = models.CharField(max_length=50, blank=True)
    # Future: subjects_taught = ManyToManyField(Subject)

    def __str__(self):
        return f"Teacher: {self.user.get_full_name()}"


class ParentProfile(TimeStampedModel):
    """
    Links a parent user to their children (StudentProfiles).
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='parent_profile'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='parent_profiles'
    )
    children = models.ManyToManyField(
        StudentProfile,
        blank=True,
        related_name='parents'
    )

    def __str__(self):
        return f"Parent: {self.user.get_full_name()}"
