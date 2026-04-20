"""
apps/accounts/views.py

Authentication & User Management views for EduSync Pro.

Flow:
  1. SuperAdmin creates org → auto-generates school admin credentials
  2. School admin logs in → forced to change password
  3. School admin adds teachers → auto-generated credentials shown once
  4. School admin adds students → auto-generated credentials shown once
  5. School admin adds parents → auto-generated credentials shown once

Security rules:
  - ALL user management scoped to request.user.organization
  - Only org_admin can create/manage users within their org
  - super_admin can create organizations
  - Credentials are shown ONCE, never stored in plaintext
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.views import View
from django.utils.text import slugify
from django.db import transaction

from core.models import Organization, AcademicYear, ClassRoom
from accounts.models import User, StudentProfile, TeacherProfile, ParentProfile
from accounts.utils import create_user_with_credentials, generate_org_admin_username
from core.views import OrgRequiredMixin, RoleRequiredMixin


# ─────────────────────────────────────────────────────────────
# AUTH: Login / Logout / Force Password Change
# ─────────────────────────────────────────────────────────────
class RegisterView(View):
    template_name = 'accounts/register.html'

    def get(self, request):
        messages.info(
            request, 'Registration is currently closed. Contact your administrator.')
        return render(request, self.template_name)


class LoginView(View):
    template_name = 'accounts/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            if request.user.must_change_password:
                return redirect('accounts:force_change_password')
            return redirect('core:dashboard')
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, self.template_name)

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(
                request, 'Invalid username or password. Please try again.')
            return render(request, self.template_name)

        if not user.is_active:
            messages.error(
                request, 'This account has been deactivated. Contact your administrator.')
            return render(request, self.template_name)

        login(request, user)

        # Intercept: force password change for auto-generated accounts
        if user.must_change_password:
            return redirect('accounts:force_change_password')

        messages.success(
            request, f'Welcome back, {user.get_full_name() or user.username}!')
        return redirect(request.GET.get('next', 'core:dashboard'))


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('accounts:login')

    def post(self, request):
        return self.get(request)


class ForceChangePasswordView(View):
    """
    Mandatory password change for auto-generated accounts.
    User CANNOT bypass this — middleware also enforces it.
    """
    template_name = 'accounts/force_change_password.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.must_change_password:
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        errors = []
        if len(new_password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if new_password != confirm_password:
            errors.append('Passwords do not match.')
        if new_password.isalnum() and len(new_password) == 10:
            errors.append(
                'Please choose a more personal password (not the system-generated one).')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, self.template_name)

        user = request.user
        user.set_password(new_password)
        user.must_change_password = False
        user.save()

        update_session_auth_hash(request, user)
        messages.success(
            request, 'Password changed successfully. Welcome to EduSync Pro!')
        return redirect('core:dashboard')


# ─────────────────────────────────────────────────────────────
# SUPERADMIN: Create Organization
# ─────────────────────────────────────────────────────────────

class CreateOrganizationView(View):
    """
    SuperAdmin creates a new school organization.
    System auto-generates the school admin credentials shown once.
    """
    template_name = 'accounts/create_organization.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_super_admin or request.user.is_staff):
            messages.error(
                request, 'Only Super Admins can create organizations.')
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        orgs = Organization.objects.all().order_by('-created_at')
        return render(request, self.template_name, {'orgs': orgs})

    @transaction.atomic
    def post(self, request):
        org_name = request.POST.get('org_name', '').strip()
        org_email = request.POST.get('org_email', '').strip()
        org_phone = request.POST.get('org_phone', '').strip()
        admin_first = request.POST.get('admin_first_name', '').strip()
        admin_last = request.POST.get('admin_last_name', '').strip()
        admin_email = request.POST.get('admin_email', '').strip()

        orgs = Organization.objects.all().order_by('-created_at')

        errors = []
        if not org_name:
            errors.append('School name is required.')
        if not admin_first or not admin_last:
            errors.append('Admin first and last name are required.')
        if Organization.objects.filter(name__iexact=org_name).exists():
            errors.append(
                f'An organization named "{org_name}" already exists.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, self.template_name, {'form_data': request.POST, 'orgs': orgs})

        # Create org
        base_slug = slugify(org_name)
        slug, counter = base_slug, 2
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        org = Organization.objects.create(
            name=org_name, slug=slug, email=org_email, phone=org_phone,
        )

        # Default academic year
        from django.utils import timezone
        year = timezone.now().year
        AcademicYear.objects.create(
            organization=org, name=f"{year}/{year+1}",
            start_date=f"{year}-01-01", end_date=f"{year+1}-12-31", is_current=True,
        )

        # Auto-generate admin credentials
        admin_username = generate_org_admin_username(slug)
        counter2 = 2
        base_uname = admin_username
        while User.objects.filter(username=admin_username).exists():
            admin_username = f"{base_uname}{counter2}"
            counter2 += 1

        from accounts.utils import generate_password
        admin_password = generate_password()

        admin_user = User.objects.create_user(
            username=admin_username, password=admin_password,
            first_name=admin_first, last_name=admin_last, email=admin_email,
            organization=org, role=User.Role.ORG_ADMIN, must_change_password=True,
        )

        return render(request, self.template_name, {
            'success': True,
            'org': org,
            'orgs': Organization.objects.all().order_by('-created_at'),
            'credentials': {
                'username': admin_username,
                'password': admin_password,
                'admin_name': admin_user.get_full_name(),
                'login_url': request.build_absolute_uri('/accounts/login/'),
            }
        })


# ─────────────────────────────────────────────────────────────
# SCHOOL ADMIN: User Management
# ─────────────────────────────────────────────────────────────

class UserListView(RoleRequiredMixin, View):
    allowed_roles = ['org_admin']
    template_name = 'accounts/user_list.html'

    def get(self, request):
        role_filter = request.GET.get('role', '')
        qs = User.objects.filter(
            organization=self.org
        ).exclude(role='super_admin').select_related('organization')

        if role_filter:
            qs = qs.filter(role=role_filter)

        context = {
            'users': qs.order_by('role', 'last_name', 'first_name'),
            'role_filter': role_filter,
            'page_title': 'Manage Users',
            'counts': {
                'teachers': User.objects.filter(organization=self.org, role='teacher').count(),
                'students': User.objects.filter(organization=self.org, role='student').count(),
                'parents':  User.objects.filter(organization=self.org, role='parent').count(),
            }
        }
        return render(request, self.template_name, context)


class AddTeacherView(RoleRequiredMixin, View):
    allowed_roles = ['org_admin']
    template_name = 'accounts/add_teacher.html'

    def get(self, request):
        return render(request, self.template_name, {'page_title': 'Add Teacher'})

    @transaction.atomic
    def post(self, request):
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        employee_no = request.POST.get('employee_number', '').strip()

        errors = []
        if not first_name or not last_name:
            errors.append('First and last name are required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, self.template_name, {
                'form_data': request.POST, 'page_title': 'Add Teacher'
            })

        user, password = create_user_with_credentials(
            first_name=first_name, last_name=last_name,
            email=email, phone=phone,
            organization=self.org, role=User.Role.TEACHER,
        )

        TeacherProfile.objects.create(
            user=user, organization=self.org, employee_number=employee_no,
        )

        return render(request, self.template_name, {
            'success': True,
            'page_title': 'Add Teacher',
            'credentials': {
                'name': user.get_full_name(),
                'username': user.username,
                'password': password,
                'role': 'Teacher',
                'login_url': request.build_absolute_uri('/accounts/login/'),
            }
        })


class AddStudentView(RoleRequiredMixin, View):
    allowed_roles = ['org_admin']
    template_name = 'accounts/add_student.html'

    def _get_classrooms(self):
        return ClassRoom.objects.filter(organization=self.org).order_by('name')

    def get(self, request):
        return render(request, self.template_name, {
            'classrooms': self._get_classrooms(),
            'page_title': 'Add Student',
        })

    @transaction.atomic
    def post(self, request):
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        classroom_id = request.POST.get('classroom', '')
        admission_no = request.POST.get('admission_number', '').strip()
        dob = request.POST.get('date_of_birth', '') or None
        classrooms = self._get_classrooms()

        errors = []
        if not first_name or not last_name:
            errors.append('First and last name are required.')
        if not classroom_id:
            errors.append('Please select a class.')

        classroom = None
        if classroom_id:
            try:
                classroom = ClassRoom.objects.get(
                    id=classroom_id, organization=self.org)
            except ClassRoom.DoesNotExist:
                errors.append('Invalid class selected.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, self.template_name, {
                'classrooms': classrooms, 'form_data': request.POST, 'page_title': 'Add Student'
            })

        user, password = create_user_with_credentials(
            first_name=first_name, last_name=last_name,
            email=email, phone=phone,
            organization=self.org, role=User.Role.STUDENT,
        )

        StudentProfile.objects.create(
            user=user, organization=self.org,
            classroom=classroom,
            admission_number=admission_no,
            date_of_birth=dob,
        )

        return render(request, self.template_name, {
            'success': True,
            'classrooms': classrooms,
            'page_title': 'Add Student',
            'credentials': {
                'name': user.get_full_name(),
                'username': user.username,
                'password': password,
                'role': 'Student',
                'classroom': classroom.name if classroom else '',
                'login_url': request.build_absolute_uri('/accounts/login/'),
            }
        })


class AddParentView(RoleRequiredMixin, View):
    allowed_roles = ['org_admin']
    template_name = 'accounts/add_parent.html'

    def _get_students(self):
        return StudentProfile.objects.filter(
            organization=self.org
        ).select_related('user', 'classroom').order_by('classroom__name', 'user__last_name')

    def get(self, request):
        return render(request, self.template_name, {
            'students': self._get_students(), 'page_title': 'Add Parent'
        })

    @transaction.atomic
    def post(self, request):
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        children_ids = request.POST.getlist('children')
        students = self._get_students()

        errors = []
        if not first_name or not last_name:
            errors.append('First and last name are required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, self.template_name, {
                'students': students, 'form_data': request.POST, 'page_title': 'Add Parent'
            })

        user, password = create_user_with_credentials(
            first_name=first_name, last_name=last_name,
            email=email, phone=phone,
            organization=self.org, role=User.Role.PARENT,
        )

        parent_profile = ParentProfile.objects.create(
            user=user, organization=self.org)

        if children_ids:
            children = StudentProfile.objects.filter(
                id__in=children_ids, organization=self.org  # tenant check
            )
            parent_profile.children.set(children)

        linked = list(parent_profile.children.select_related('user'))

        return render(request, self.template_name, {
            'success': True,
            'students': students,
            'page_title': 'Add Parent',
            'credentials': {
                'name': user.get_full_name(),
                'username': user.username,
                'password': password,
                'role': 'Parent',
                'children': [c.user.get_full_name() for c in linked],
                'login_url': request.build_absolute_uri('/accounts/login/'),
            }
        })


class ToggleUserActiveView(RoleRequiredMixin, View):
    allowed_roles = ['org_admin']

    def post(self, request, user_id):
        target = get_object_or_404(User, id=user_id, organization=self.org)
        if target == request.user:
            messages.error(request, 'You cannot deactivate your own account.')
            return redirect('accounts:user_list')
        target.is_active = not target.is_active
        target.save()
        messages.success(
            request,
            f'{target.get_full_name()} has been {"activated" if target.is_active else "deactivated"}.'
        )
        return redirect('accounts:user_list')


class ResetUserPasswordView(RoleRequiredMixin, View):
    allowed_roles = ['org_admin']
    template_name = 'accounts/reset_password_confirm.html'

    def post(self, request, user_id):
        from accounts.utils import generate_password
        target = get_object_or_404(User, id=user_id, organization=self.org)
        new_password = generate_password()
        target.set_password(new_password)
        target.must_change_password = True
        target.save()
        return render(request, self.template_name, {
            'target_user': target,
            'new_password': new_password,
            'page_title': 'Password Reset',
        })
