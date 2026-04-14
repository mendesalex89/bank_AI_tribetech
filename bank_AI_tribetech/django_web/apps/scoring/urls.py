from django.urls import path
from . import views

urlpatterns = [
    path("pd/",    views.scoring_pd,    name="scoring_pd"),
    path("lgd/",   views.scoring_lgd,   name="scoring_lgd"),
    path("ead/",   views.scoring_ead,   name="scoring_ead"),
    path("batch/", views.scoring_batch, name="scoring_batch"),
    path("api/predict/pd/",  views.api_predict_pd,  name="api_predict_pd"),
    path("api/predict/lgd/", views.api_predict_lgd, name="api_predict_lgd"),
    path("api/predict/ead/", views.api_predict_ead, name="api_predict_ead"),
    path("api/batch/upload/", views.api_batch_upload, name="api_batch_upload"),
]
