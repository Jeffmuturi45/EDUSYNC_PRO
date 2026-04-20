from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import User, StudentProfile, TeacherProfile, ParentProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'get_full_name',
                    'role', 'organization', 'is_active']
    list_filter = ['role', 'organization', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('EduSync Pro', {'fields': ('organization', 'role', 'phone')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('EduSync Pro', {'fields': ('organization', 'role')}),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'classroom', 'admission_number']
    list_filter = ['organization', 'classroom']
    search_fields = ['user__first_name', 'user__last_name', 'admission_number']


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'employee_number']
    list_filter = ['organization']


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization']
    list_filter = ['organization']
