from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    # path('dashboard/', include('dashboard.urls', namespace='core')),
    path('exams/', include('exams.urls', namespace='exams')),
    # path('api/exams/', include('exams.api.urls', namespace='exams_api')),
    path('', lambda r: redirect('dashboard/')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
