"""
apps/core/views.py

Core views for EduSync Pro.

OrgRequiredMixin — the security backbone.
  Every protected view must inherit this.
  It enforces:
    1. User is authenticated
    2. User belongs to an organization (super admins are exempt)
    3. Sets self.org for convenient use in child views

DashboardView — Role-aware landing page.
  Renders different stats/widgets per role.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.urls import reverse
from django.db.models import Count, Q

from core.models import Organization, ClassRoom, Subject


class OrgRequiredMixin(LoginRequiredMixin):
    """
    SECURITY MIXIN — inherit in every protected view.

    Guarantees:
    - User is logged in (redirects to login if not)
    - User has an organization (no orphan users — super_admin exempt)
    - self.org is set for all child views

    Usage:
        class MyView(OrgRequiredMixin, View):
            def get(self, request):
                qs = MyModel.objects.filter(organization=self.org)
    """
    login_url = '/accounts/login/'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Super admins have no org — they manage the platform itself
        if request.user.is_super_admin:
            self.org = None
            return super().dispatch(request, *args, **kwargs)

        if not request.user.organization:
            messages.error(
                request, 'Your account is not linked to any organization.')
            return redirect(reverse('accounts:login'))

        self.org = request.user.organization
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin(OrgRequiredMixin):
    """
    Extends OrgRequiredMixin with role enforcement.
    Set `allowed_roles` on the child view class.

    Example:
        class AdminOnlyView(RoleRequiredMixin, View):
            allowed_roles = ['org_admin']
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        # If super already redirected, return that
        if hasattr(result, 'status_code') and result.status_code in (301, 302):
            return result

        if self.allowed_roles and request.user.role not in self.allowed_roles:
            messages.error(
                request, 'You do not have permission to access this page.')
            return redirect(reverse('core:dashboard'))

        return result


# ─────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────

class DashboardView(OrgRequiredMixin, View):
    """
    Role-aware dashboard.
    Each role sees relevant stats and quick actions.

    Roles:
      super_admin  → platform overview: all orgs, org creation CTA
      org_admin    → school overview: staff counts, exam review queue
      teacher      → own exams, class list
      student      → published results in their class
      parent       → children's results
    """

    def get(self, request):
        user = request.user
        context = {'page_title': 'Dashboard'}

        if user.is_super_admin:
            context.update(self._super_admin_context(request))
            return render(request, 'dashboard/super_admin_dashboard.html', context)

        elif user.is_org_admin:
            context.update(self._admin_context(request))
            return render(request, 'dashboard/admin_dashboard.html', context)

        elif user.is_teacher:
            context.update(self._teacher_context(request))
            return render(request, 'dashboard/teacher_dashboard.html', context)

        elif user.is_student:
            context.update(self._student_context(request))
            return render(request, 'dashboard/student_dashboard.html', context)

        elif user.is_parent:
            context.update(self._parent_context(request))
            return render(request, 'dashboard/parent_dashboard.html', context)

        # Fallback — should never hit this for a properly assigned user
        messages.warning(
            request, 'Your account role is not configured. Contact support.')
        return redirect(reverse('accounts:login'))

    def _super_admin_context(self, request):
        """Platform-level stats for the super admin."""
        orgs = Organization.objects.all().order_by('-created_at')
        return {
            'page_title': 'Platform Overview',
            'stats': {
                'total_orgs':   orgs.count(),
                'active_orgs':  orgs.filter(is_active=True).count(),
                'inactive_orgs': orgs.filter(is_active=False).count(),
            },
            'recent_orgs': orgs[:10],
        }

    def _admin_context(self, request):
        from exams.models import Exam
        from accounts.models import User as AppUser

        org = self.org
        exams = Exam.objects.filter(organization=org)

        return {
            'stats': {
                'total_students': AppUser.objects.filter(organization=org, role='student').count(),
                'total_teachers': AppUser.objects.filter(organization=org, role='teacher').count(),
                'total_classes':  ClassRoom.objects.filter(organization=org).count(),
                'total_subjects': Subject.objects.filter(organization=org).count(),
                'exams_draft':      exams.filter(status='draft').count(),
                'exams_submitted':  exams.filter(status='submitted').count(),
                'exams_published':  exams.filter(status='published').count(),
            },
            'pending_exams': exams.filter(status='submitted').select_related(
                'classroom', 'created_by'
            )[:5],
            'recent_exams': exams.order_by('-created_at').select_related(
                'classroom', 'created_by'
            )[:5],
        }

    def _teacher_context(self, request):
        from exams.models import Exam

        org = self.org
        my_exams = Exam.objects.filter(
            organization=org,
            created_by=request.user
        ).select_related('classroom')

        return {
            'stats': {
                'my_drafts':     my_exams.filter(status='draft').count(),
                'my_submitted':  my_exams.filter(status='submitted').count(),
                'my_published':  my_exams.filter(status='published').count(),
                'total_classes': ClassRoom.objects.filter(organization=org).count(),
            },
            'recent_exams': my_exams.order_by('-created_at')[:6],
            'classes': ClassRoom.objects.filter(organization=org),
        }

    def _student_context(self, request):
        from exams.models import Exam, ExamResult

        try:
            classroom = request.user.student_profile.classroom
        except Exception:
            classroom = None

        published_exams = Exam.objects.filter(
            organization=self.org,
            status='published',
            classroom=classroom
        ).order_by('-published_at') if classroom else []

        return {
            'classroom': classroom,
            'published_exams': published_exams[:5],
            'stats': {
                'total_results': ExamResult.objects.filter(
                    student=request.user,
                    exam__status='published'
                ).count(),
            }
        }

    def _parent_context(self, request):
        try:
            children = request.user.parent_profile.children.select_related(
                'user', 'classroom'
            )
        except Exception:
            children = []

        return {
            'children': children,
            'stats': {
                'total_children': len(children) if hasattr(children, '__len__') else children.count(),
            }
        }
