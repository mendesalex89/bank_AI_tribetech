"""
URLs — Credit Risk IRB Platform
TribeTech | 2026
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.home.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("scoring/", include("apps.scoring.urls")),
    path("relatorios/", include("apps.reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
