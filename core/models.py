"""
core/models.py

Foundation models for EduSync Pro multi-tenant system.
Every data model in the system references Organization as the
tenant boundary - this is the #1 security guarantee.
"""
import uuid
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Abstract base: gives every model created_at + updated_at.
    Inherit from this instead of models.Model everywhere.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    """
    The TENANT. Every school/institution gets one Organization.
    All data is scoped to this - the entire multi-tenancy rests here.

    Design note: We use a simple FK pattern (shared schema, row-level
    isolation) rather than separate schemas per tenant. This is simpler
    to maintain and sufficient for this scale.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200, help_text="School/Institution name")
    slug = models.SlugField(
        unique=True, help_text="URL-safe identifier e.g. 'st-marys-high'")
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    # Future: billing plan, subscription tier
    # plan = models.CharField(choices=PLAN_CHOICES, default='free')

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ['name']

    def __str__(self):
        return self.name


class AcademicYear(TimeStampedModel):
    """
    Academic year scoped per organization.
    e.g. "2024/2025", "2025"
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='academic_years'
    )
    name = models.CharField(max_length=20, help_text="e.g. 2024/2025")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        unique_together = ['organization', 'name']
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.organization.name} — {self.name}"

    def save(self, *args, **kwargs):
        # Ensure only one current year per org
        if self.is_current:
            AcademicYear.objects.filter(
                organization=self.organization,
                is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class ClassRoom(TimeStampedModel):
    """
    A class/grade within an organization.
    e.g. "Form 1A", "Grade 6 East", "JSS 2B"

    Design note: Kept simple. Can be extended with
    streams, sections, capacity limits later.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='classrooms'
    )
    name = models.CharField(max_length=100, help_text="e.g. Form 1A, Grade 6")
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classrooms'
    )
    # Future: class teacher assignment
    # class_teacher = models.ForeignKey('accounts.User', ...)

    class Meta:
        unique_together = ['organization', 'name', 'academic_year']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class Subject(TimeStampedModel):
    """
    Subjects offered by an organization.
    e.g. Mathematics, English, Biology
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='subjects'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True,
                            help_text="e.g. MATH101")
    # Future: subject category (core/elective), credit hours

    class Meta:
        unique_together = ['organization', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name})"
