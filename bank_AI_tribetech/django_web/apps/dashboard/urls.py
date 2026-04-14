from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/portfolio/",       views.api_portfolio,       name="api_portfolio"),
    path("api/defaults/",        views.api_defaults,        name="api_defaults"),
    path("api/grade-dist/",      views.api_grade_dist,      name="api_grade_dist"),
    path("api/kpis/",            views.api_summary_kpis,    name="api_summary_kpis"),
    path("api/vintage/",         views.api_vintage,         name="api_vintage"),
    path("api/fico/",            views.api_fico_distribution, name="api_fico_dist"),
    path("api/el-grade/",        views.api_el_by_grade,     name="api_el_grade"),
    path("api/model-metrics/",   views.api_model_metrics,   name="api_model_metrics"),
]
