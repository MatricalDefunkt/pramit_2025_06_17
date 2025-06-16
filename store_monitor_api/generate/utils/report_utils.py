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

from celery import shared_task, group, chord
from celery.utils.log import get_task_logger
from django.core.cache import cache
import pandas as pd
from .database_utils import _load_all_data
from .metrics_utils import _process_single_store_metrics
from store_monitor_api.models import Report
from django.utils import timezone
from .time_utils import get_current_utc_time

logger = get_task_logger(__name__)


@shared_task
def process_store_chunk_task(
    store_ids_chunk,
    current_time_utc_str,  # Pass as string to avoid serialization issues
    report_id,
):
    """
    Process a chunk of store IDs and return their report lines.
    This is the 'map' part of map-reduce.
    """
    logger = get_task_logger(__name__)
    logger.info(
        f"Processing chunk of {len(store_ids_chunk)} stores for report {report_id}"
    )

    try:
        # Load data (could be optimized with caching)
        store_statuses_df, business_hours_df, timezones_df = _load_all_data()

        # Convert time string back to datetime
        from datetime import datetime
        import pytz

        current_time_utc = datetime.fromisoformat(
            current_time_utc_str.replace("Z", "+00:00")
        )

        # Ensure timestamp_utc is datetime and UTC localized
        if not store_statuses_df.empty:
            store_statuses_df["timestamp_utc"] = pd.to_datetime(
                store_statuses_df["timestamp_utc"]
            )
            if store_statuses_df["timestamp_utc"].dt.tz is None:
                store_statuses_df["timestamp_utc"] = store_statuses_df[
                    "timestamp_utc"
                ].dt.tz_localize("UTC")
            else:
                store_statuses_df["timestamp_utc"] = store_statuses_df[
                    "timestamp_utc"
                ].dt.tz_convert("UTC")

        chunk_results = []

        for store_id in store_ids_chunk:
            try:
                report_line = _process_single_store_metrics(
                    store_id,
                    store_statuses_df,
                    business_hours_df,
                    timezones_df,
                    current_time_utc,
                    cache,  # This might need adjustment for distributed caching
                    logger,
                )
                chunk_results.append(report_line)
            except KeyError as e:
                logger.error(f"KeyError processing store {store_id}: {e}")
                logger.error(
                    f"Store statuses columns: {store_statuses_df.columns.tolist() if not store_statuses_df.empty else 'EMPTY'}"
                )
                logger.error(
                    f"Business hours columns: {business_hours_df.columns.tolist() if not business_hours_df.empty else 'EMPTY'}"
                )
                logger.error(
                    f"Timezones columns: {timezones_df.columns.tolist() if not timezones_df.empty else 'EMPTY'}"
                )
                # Continue with other stores instead of failing the entire chunk
                continue

        logger.info(f"Completed chunk of {len(store_ids_chunk)} stores")
        return chunk_results

    except Exception as e:
        logger.error(
            f"Error processing chunk for report {report_id}: {e}", exc_info=True
        )
        raise


@shared_task
def combine_report_results(chunk_results_list, report_id):
    """
    Combine results from all chunks and save the final report.
    This is the 'reduce' part of map-reduce.
    """
    logger = get_task_logger(__name__)
    logger.info(
        f"Combining results from {len(chunk_results_list)} chunks for report {report_id}"
    )

    try:
        report = Report.objects.get(report_id=report_id)

        # Flatten all chunk results
        all_report_lines = [
            "store_id,uptime_last_hour,uptime_last_day,uptime_last_week,downtime_last_hour,downtime_last_day,downtime_last_week"
        ]

        for chunk_results in chunk_results_list:
            if chunk_results:  # Check if chunk returned results
                all_report_lines.extend(chunk_results)

        report.report_data = "\n".join(all_report_lines)
        report.status = "Complete"
        report.completed_at = timezone.now()
        report.save()

        logger.info(
            f"Report {report_id} completed successfully with {len(all_report_lines)-1} stores"
        )
        return f"Report {report_id} completed with {len(all_report_lines)-1} stores"

    except Exception as e:
        logger.error(
            f"Error combining results for report {report_id}: {e}", exc_info=True
        )
        # Update report status to failed
        try:
            report = Report.objects.get(report_id=report_id)
            report.status = "Failed"
            report.report_data = f"Error combining results: {str(e)}"
            report.completed_at = timezone.now()
            report.save()
        except:
            pass
        raise


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
            logger.warning("StoreStatus data is empty.")
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
