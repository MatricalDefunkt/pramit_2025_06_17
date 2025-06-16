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

from django.shortcuts import render
from django.http import JsonResponse
import uuid

from .generate.sequential import generate_report_task
from .generate.parallel import generate_report_parallel_task
from .generate.utils import load_csv_data_parallel_task
from .models import Report

# Create your views here.


def trigger_report(request):
    report_id = str(uuid.uuid4())
    Report.objects.create(report_id=report_id, status="Running")

    # Use parallel processing for large datasets
    # chunk_size = int(
    #     request.GET.get("chunk_size", 100)
    # )  # Allow configurable chunk size
    generate_report_task.delay(report_id)  # type: ignore

    return JsonResponse({"report_id": report_id})


def trigger_report_parallel(request):
    report_id = str(uuid.uuid4())
    Report.objects.create(report_id=report_id, status="Running")

    # Use parallel processing for large datasets
    chunk_size = int(
        request.GET.get("chunk_size", 100)
    )  # Allow configurable chunk size
    generate_report_parallel_task.delay(report_id, chunk_size)  # type: ignore

    return JsonResponse({"report_id": report_id})


def get_report(request, report_id):
    try:
        report = Report.objects.get(report_id=report_id)
        if report.status == "Complete":
            # In a real scenario, you would serve the CSV file here
            # For now, we return the content directly or a link
            return JsonResponse(
                {"status": "Complete", "report_csv": report.report_data}
            )
        else:
            return JsonResponse({"status": report.status})
    except Report.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)


def load_data_parallel(request):
    """
    Trigger parallel CSV data loading.
    """
    chunk_size = int(request.GET.get("chunk_size", 10000))

    try:
        # Start the parallel loading task
        result = load_csv_data_parallel_task.delay(chunk_size)  # type: ignore

        return JsonResponse(
            {
                "status": "started",
                "task_id": result.id,
                "chunk_size": chunk_size,
                "message": "Parallel data loading started. Monitor progress in Celery worker logs.",
            }
        )

    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)
