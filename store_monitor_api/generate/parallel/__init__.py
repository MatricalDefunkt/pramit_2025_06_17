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

from django.utils import timezone
from celery import shared_task, group, chord
from celery.utils.log import get_task_logger

from store_monitor_api.models import Report
from store_monitor_api.generate.utils import _load_all_data, get_current_utc_time
from store_monitor_api.generate.utils.report_utils import (
    process_store_chunk_task,
    combine_report_results,
)

logger = get_task_logger(__name__)


@shared_task
def generate_report_parallel_task(report_id: str, chunk_size: int = 100):
    """
    Generate report using parallel processing across multiple workers.
    """
    logger = get_task_logger(__name__)

    try:
        report = Report.objects.get(report_id=report_id)
        report.status = "Running"
        report.save()

        logger.info(f"Starting parallel report generation for report_id: {report_id}")

        # Load minimal data to get store IDs
        store_statuses_df, _, _ = _load_all_data()

        if store_statuses_df.empty:
            report.status = "Failed"
            report.report_data = "StoreStatus data is empty."
            report.completed_at = timezone.now()
            report.save()
            return

        all_store_ids = store_statuses_df["store_id"].unique().tolist()
        current_time_utc = get_current_utc_time()
        current_time_utc_str = current_time_utc.isoformat()

        logger.info(f"Processing {len(all_store_ids)} stores in chunks of {chunk_size}")

        # Split store IDs into chunks
        store_chunks = [
            all_store_ids[i : i + chunk_size]
            for i in range(0, len(all_store_ids), chunk_size)
        ]

        logger.info(f"Created {len(store_chunks)} chunks for parallel processing")

        # Create a chord: group of parallel tasks followed by a callback
        job = chord(
            group(
                process_store_chunk_task.s(chunk, current_time_utc_str, report_id)  # type: ignore
                for chunk in store_chunks
            )
        )(
            combine_report_results.s(report_id)  # type: ignore
        )  # type: ignore

        logger.info(f"Dispatched parallel processing job for report {report_id}")
        return f"Parallel processing started for report {report_id} with {len(store_chunks)} chunks"

    except Exception as e:
        logger.error(f"Error starting parallel report {report_id}: {e}", exc_info=True)
        try:
            report = Report.objects.get(report_id=report_id)
            report.status = "Failed"
            report.report_data = f"Error: {str(e)}"
            report.completed_at = timezone.now()
            report.save()
        except:
            pass
        raise
