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

from django.db import models

# Create your models here.


class StoreStatus(models.Model):
    store_id = models.CharField(max_length=36, null=False, blank=False)
    timestamp_utc = models.DateTimeField()

    class StatusChoices(models.TextChoices):
        ACTIVE = "active"
        INACTIVE = "inactive"

    status = models.CharField(
        max_length=10,  # Sufficient for 'active' or 'inactive'
        choices=StatusChoices.choices,
    )

    class Meta:
        indexes = [
            models.Index(fields=["store_id", "timestamp_utc"]),
        ]


class BusinessHours(models.Model):
    store_id = models.CharField(max_length=36, primary_key=True)
    day_of_week = models.IntegerField()  # 0=Monday, 6=Sunday
    start_time_local = models.TimeField()
    end_time_local = models.TimeField()

    class Meta:
        unique_together = (
            "store_id",
            "day_of_week",
            "start_time_local",
            "end_time_local",
        )
        indexes = [
            models.Index(fields=["store_id", "day_of_week"]),
        ]


class StoreTimezone(models.Model):
    store_id = models.CharField(max_length=36, primary_key=True)
    timezone_str = models.CharField(max_length=50, default="America/Chicago")


class Report(models.Model):
    report_id = models.CharField(max_length=255, primary_key=True)
    status = models.CharField(
        max_length=20,
        default="Running",
        choices=[
            ("Running", "Running"),
            ("Complete", "Complete"),
            ("Failed", "Failed"),
        ],
    )  # Running, Complete, Failed
    report_data = models.TextField(
        null=True, blank=True
    )  # Stores CSV data or error message
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
