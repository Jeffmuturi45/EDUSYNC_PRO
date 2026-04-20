"""
apps/core/middleware.py

OrganizationMiddleware — attaches org to request.
Also enforces must_change_password redirect on all protected routes.
"""
from django.shortcuts import redirect


class OrganizationMiddleware:
    SKIP_PATHS = ['/admin/', '/static/', '/media/']
    # Paths allowed even when must_change_password=True
    ALLOW_PATHS = ['/accounts/login/',
                   '/accounts/logout/', '/accounts/change-password/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Attach org to every request
        if any(request.path.startswith(p) for p in self.SKIP_PATHS):
            request.organization = None
            return self.get_response(request)

        if request.user.is_authenticated:
            request.organization = getattr(request.user, 'organization', None)

            # Enforce password change before ANY other page
            if (
                request.user.must_change_password
                and not any(request.path.startswith(p) for p in self.ALLOW_PATHS)
            ):
                return redirect('/accounts/change-password/')
        else:
            request.organization = None

        return self.get_response(request)
