"""
apps/core/context_processors.py

Injects organization + brand data into every template context.
"""
from django.conf import settings


def organization_context(request):
    """
    Available in every template:
    - {{ organization }}   — current org object (None for super_admin)
    - {{ brand }}          — color + name config
    - {{ is_org_admin }}   — True if school admin
    - {{ is_teacher }}
    - {{ is_student }}
    - {{ is_parent }}
    - {{ is_super_admin }} — FIX: was missing, caused sidebar to hide super admin nav
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
        # FIX: was missing
        context['is_super_admin'] = request.user.is_super_admin

    return context
