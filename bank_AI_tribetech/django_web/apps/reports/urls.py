from django.urls import path
from . import views

urlpatterns = [
    path("eba/",         views.reports_eba,        name="reports_eba"),
    path("monitorizacao/", views.reports_monitoring, name="reports_monitoring"),
    path("api/metrics/", views.api_metrics,         name="api_metrics"),
    path("pdf/gerar/",   views.generate_pdf,        name="generate_pdf"),
]
