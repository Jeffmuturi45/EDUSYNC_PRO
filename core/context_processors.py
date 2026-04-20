"""
apps/core/context_processors.py

Injects organization + brand data into every template context.
"""
from django.conf import settings


def organization_context(request):
    """
    Available in every template:
    - {{ organization }} — current org object
    - {{ brand }} — color + name config
    - {{ user_role }} — shortcut for role checks
    """
    context = {
        'organization': getattr(request, 'organization', None),
        'brand': settings.EDUSYNC_BRAND,
    }

    if request.user.is_authenticated:
        context['user_role'] = request.user.role
        context['is_org_admin'] = request.user.is_org_admin
        context['is_teacher'] = request.user.is_teacher
        context['is_student'] = request.user.is_student
        context['is_parent'] = request.user.is_parent

    return context
