# Store Monitor API - A tool for monitoring store performance and uptime.
# Copyright (C) 2025 Pramit Sharma
#
# This file is part of pramit_2025_06_17.
#
# pramit_2025_06_17 is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# pramit_2025_06_17 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
