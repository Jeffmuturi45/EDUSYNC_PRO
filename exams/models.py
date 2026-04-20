"""
apps/exams/models.py

The Exams & Grading Engine - Core of EduSync Pro.

Design decisions:
1. Exam is the root entity, scoped by organization
2. ExamSubject defines what subjects are in an exam and their max scores
3. ExamResult is the atomic grade entry (student × subject × score)
4. ExamSubmissionLog provides full audit trail
5. Models are designed to support future: grade boundaries, GPA, rankings, PDF cards
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import Organization, TimeStampedModel, ClassRoom


class Exam(TimeStampedModel):
    """
    The top-level exam entity.

    Status lifecycle:
        draft → submitted → published
                         ↘ rejected → draft

    Security: ALWAYS filter by organization before any query.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted for Review'
        PUBLISHED = 'published', 'Published'
        REJECTED = 'rejected', 'Rejected'

    class Term(models.TextChoices):
        TERM_1 = 'term_1', 'Term 1'
        TERM_2 = 'term_2', 'Term 2'
        TERM_3 = 'term_3', 'Term 3'
        SEMESTER_1 = 'sem_1', 'Semester 1'
        SEMESTER_2 = 'sem_2', 'Semester 2'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Tenant isolation ─────────────────────────
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='exams'
    )

    # ── Exam metadata ────────────────────────────
    name = models.CharField(
        max_length=200,
        help_text="e.g. Midterm Exam, End of Term 1"
    )
    term = models.CharField(max_length=20, choices=Term.choices)
    academic_year = models.CharField(
        max_length=20,
        help_text="e.g. 2024/2025"
    )
    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name='exams'
    )

    # ── Workflow ─────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exams'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    rejection_note = models.TextField(
        blank=True,
        help_text="Admin feedback when rejecting an exam"
    )

    # ── Future extensibility fields ──────────────
    # These are intentionally sparse now but allow future features:
    # grade_scheme = FK(GradeScheme)  → for A/B/C grade boundaries
    # is_cumulative = BooleanField    → for combined term exams
    # weight = DecimalField           → for weighted average GPA

    class Meta:
        ordering = ['-created_at']
        # Prevent duplicate exam names per class per term per year
        unique_together = ['organization', 'classroom',
                           'name', 'term', 'academic_year']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'classroom']),
        ]

    def __str__(self):
        return f"{self.name} — {self.classroom} ({self.term})"

    @property
    def is_editable(self):
        """Only draft exams can be edited by teachers."""
        return self.status == self.Status.DRAFT

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    def get_total_max_score(self):
        """Sum of all subject max scores — used for report card totals."""
        return self.subjects.aggregate(
            total=models.Sum('max_score')
        )['total'] or 0


class ExamSubject(TimeStampedModel):
    """
    Links a subject to an exam with a maximum score.
    This defines the COLUMNS in the grading grid.

    Design: We store subject_name as a string (not FK) intentionally
    to preserve historical data if subjects are renamed/deleted.
    The subject FK is optional for linking to live Subject catalog.
    """
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='subjects'
    )
    # Store name directly for historical integrity
    subject_name = models.CharField(max_length=100)

    # Optional FK to Subject catalog (for future analytics)
    subject_ref = models.ForeignKey(
        'core.Subject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_subjects'
    )
    max_score = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    # Future: weight for weighted average, display_order
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'subject_name']
        unique_together = ['exam', 'subject_name']

    def __str__(self):
        return f"{self.subject_name} (max: {self.max_score}) — {self.exam}"


class ExamResult(TimeStampedModel):
    """
    A single student's score for one subject in one exam.
    This is the CELL in the grading grid.

    Design:
    - Composite uniqueness: one score per (exam, student, subject)
    - score=None means not yet entered (different from 0)
    - Use update_or_create for idempotent saves
    """
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='results'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_results'
    )
    subject = models.ForeignKey(
        ExamSubject,
        on_delete=models.CASCADE,
        related_name='results'
    )
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="null = not yet entered, 0 = scored zero"
    )

    # Future fields (models ready, not yet used):
    # grade = models.CharField(max_length=5, blank=True)  # A, B, C
    # grade_points = models.DecimalField(...)              # 4.0, 3.5...
    # remarks = models.TextField(blank=True)               # Teacher comments
    # is_absent = models.BooleanField(default=False)

    class Meta:
        unique_together = ['exam', 'student', 'subject']
        indexes = [
            models.Index(fields=['exam', 'student']),
            models.Index(fields=['exam', 'subject']),
        ]

    def __str__(self):
        return (
            f"{self.student.get_full_name()} | "
            f"{self.subject.subject_name}: {self.score}"
        )

    @property
    def percentage(self):
        """Score as percentage of max_score. Used for future grade calculation."""
        if self.score is not None and self.subject.max_score:
            return round((float(self.score) / self.subject.max_score) * 100, 1)
        return None


class ExamSubmissionLog(TimeStampedModel):
    """
    Full audit trail for exam workflow transitions.
    Who did what and when — required for accountability.

    Future: This can feed an analytics dashboard for admin insights.
    """

    class Action(models.TextChoices):
        DRAFT_SAVED = 'draft_saved', 'Draft Saved'
        SUBMITTED = 'submitted', 'Submitted for Review'
        APPROVED = 'approved', 'Approved & Published'
        REJECTED = 'rejected', 'Rejected'
        REOPENED = 'reopened', 'Reopened for Editing'

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='submission_logs'
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='exam_actions'
    )
    note = models.TextField(
        blank=True,
        help_text="Optional note (e.g. rejection reason)"
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.exam} | {self.action} "
            f"by {self.performed_by} at {self.created_at:%Y-%m-%d %H:%M}"
        )
