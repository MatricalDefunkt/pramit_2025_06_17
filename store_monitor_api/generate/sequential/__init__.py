from typing import Union
import pandas as pd
from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.cache import cache
from django.utils import timezone

from store_monitor_api.models import Report
from store_monitor_api.generate.utils import (
    _load_all_data,
    _process_single_store_metrics,
    get_current_utc_time,
)

logger = get_task_logger(__name__)


@shared_task
def generate_report_task(report_id: str):
    report: Union[Report, None] = None
    try:
        report = Report.objects.get(report_id=report_id)
        report.status = "Running"
        report.save()
        logger.info(f"Starting report generation for report_id: {report_id}")

        store_statuses_df, business_hours_df, timezones_df = _load_all_data()

        if store_statuses_df.empty:
            if report:
                report.status = "Failed"
                report.report_data = "StoreStatus data is empty."
                report.completed_at = timezone.now()
                report.save()
            return

        # Ensure timestamp_utc is datetime and UTC localized
        if not store_statuses_df.empty:
            store_statuses_df["timestamp_utc"] = pd.to_datetime(
                store_statuses_df["timestamp_utc"]
            )
            if store_statuses_df["timestamp_utc"].dt.tz is None:
                store_statuses_df["timestamp_utc"] = store_statuses_df[
                    "timestamp_utc"
                ].dt.tz_localize("UTC", ambiguous="raise", nonexistent="raise")
            else:
                store_statuses_df["timestamp_utc"] = store_statuses_df[
                    "timestamp_utc"
                ].dt.tz_convert("UTC")

        current_time_utc = get_current_utc_time()
        logger.info(
            f"Using current_time_utc: {current_time_utc} for report: {report_id}"
        )

        report_lines = [
            "store_id,uptime_last_hour,uptime_last_day,uptime_last_week,downtime_last_hour,downtime_last_day,downtime_last_week"
        ]

        if store_statuses_df.empty or "store_id" not in store_statuses_df.columns:
            logger.error(
                "Cannot get store IDs - store_statuses_df is empty or missing store_id column"
            )
            if report:
                report.status = "Failed"
                report.report_data = "Cannot get store IDs - store_statuses_df is empty or missing store_id column"
                report.completed_at = timezone.now()
                report.save()
            return

        all_store_ids = store_statuses_df["store_id"].unique()

        for store_id in all_store_ids:
            current_store_id: str = store_id

            cache_key = f"report_store_{current_store_id}_{current_time_utc.strftime('%Y%m%d%H%M%S')}"
            cached_result = cache.get(cache_key)

            if cached_result:
                logger.info(f"Using cached result for store_id: {current_store_id}")
                report_lines.append(cached_result)
                continue

            report_line_for_store = _process_single_store_metrics(
                current_store_id,
                store_statuses_df,  # Pass the full DF
                business_hours_df,  # Pass the full DF
                timezones_df,  # Pass the full DF
                current_time_utc,
                cache,
                logger,
            )
            report_lines.append(report_line_for_store)
            cache.set(
                cache_key, report_line_for_store, timeout=3600
            )  # Cache for 1 hour

        if report:
            report.report_data = "\\n".join(report_lines)
            report.status = "Complete"
            report.completed_at = timezone.now()
            report.save()
        logger.info(f"Report {report_id} completed successfully.")

    except Exception as e:
        logger.error(f"Error generating report {report_id}: {e}", exc_info=True)
        if report:
            report.status = "Failed"
            report.report_data = f"Error: {str(e)}"
            report.completed_at = timezone.now()
            report.save()
        raise
