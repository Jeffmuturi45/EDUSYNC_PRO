from django.contrib import admin
from exams.models import Exam, ExamSubject, ExamResult, ExamSubmissionLog


class ExamSubjectInline(admin.TabularInline):
    model = ExamSubject
    extra = 1
    fields = ['subject_name', 'max_score', 'order']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'classroom',
                    'term', 'status', 'created_by', 'created_at']
    list_filter = ['organization', 'status', 'term']
    search_fields = ['name']
    inlines = [ExamSubjectInline]
    readonly_fields = ['created_at', 'updated_at',
                       'submitted_at', 'published_at']


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ['exam', 'student', 'subject', 'score']
    list_filter = ['exam__organization', 'exam__status']
    search_fields = ['student__first_name', 'student__last_name']


@admin.register(ExamSubmissionLog)
class ExamSubmissionLogAdmin(admin.ModelAdmin):
    list_display = ['exam', 'action', 'performed_by', 'created_at']
    list_filter = ['action']
    readonly_fields = ['created_at']
