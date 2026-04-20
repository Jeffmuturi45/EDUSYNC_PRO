from django.contrib import admin
from core.models import Organization, AcademicYear, ClassRoom, Subject


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'email', 'is_active', 'created_at']
    search_fields = ['name', 'email']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization',
                    'is_current', 'start_date', 'end_date']
    list_filter = ['organization', 'is_current']


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'academic_year']
    list_filter = ['organization', 'academic_year']
    search_fields = ['name']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'organization']
    list_filter = ['organization']
    search_fields = ['name', 'code']
