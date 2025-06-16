from django.contrib import admin
from django.urls import path, include
from .views import health_check

urlpatterns = [
    path("api/", include("store_monitor_api.urls")),
    path("", health_check),
]
