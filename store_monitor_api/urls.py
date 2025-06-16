from django.urls import path
from . import views

urlpatterns = [
    path("trigger_report/", views.trigger_report, name="trigger_report"),
    path(
        "trigger_report_parallel/",
        views.trigger_report_parallel,
        name="trigger_report_parallel",
    ),
    path("get_report/<str:report_id>/", views.get_report, name="get_report"),
    path("load_data_parallel/", views.load_data_parallel, name="load_data_parallel"),
]
