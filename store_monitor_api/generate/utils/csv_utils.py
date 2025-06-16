from celery import shared_task, group, chord
from celery.utils.log import get_task_logger
import csv
from django.db import transaction
from django.conf import settings
import pytz
from store_monitor_api.models import StoreStatus, BusinessHours, StoreTimezone
from datetime import datetime

logger = get_task_logger(__name__)

# Current loading strategy does not work with celery


@shared_task
def load_store_status_chunk_task(chunk_start: int, chunk_size: int):
    """
    Load a chunk of store status data from CSV.
    """
    logger.info(
        f"Loading store status chunk: rows {chunk_start} to {chunk_start + chunk_size}"
    )

    try:
        base_data_path = settings.BASE_DIR.parent / "docs"
        store_status_csv = base_data_path / "store_status.csv"

        store_statuses_to_create = []

        with open(store_status_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Skip to the starting row
            for _ in range(chunk_start):
                try:
                    next(reader)
                except StopIteration:
                    logger.info(f"Reached end of file at row {chunk_start}")
                    return 0

            # Process chunk_size rows
            rows_processed = 0
            for row in reader:
                if rows_processed >= chunk_size:
                    break

                try:
                    store_id = row["store_id"]
                    timestamp_str = row["timestamp_utc"]

                    # Parse timestamp
                    try:
                        dt_obj = datetime.strptime(
                            timestamp_str, "%Y-%m-%d %H:%M:%S.%f %Z"
                        )
                    except ValueError:
                        dt_obj = datetime.strptime(
                            timestamp_str, "%Y-%m-%d %H:%M:%S %Z"
                        )

                    ts_utc = pytz.utc.localize(dt_obj)
                    status = row["status"]

                    if status not in ["active", "inactive"]:
                        logger.warning(f"Skipping row with invalid status: {row}")
                        continue

                    store_statuses_to_create.append(
                        StoreStatus(
                            store_id=store_id, timestamp_utc=ts_utc, status=status
                        )
                    )
                    rows_processed += 1

                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping row due to error: {row} - {e}")

        # Bulk create the chunk
        if store_statuses_to_create:
            with transaction.atomic():
                StoreStatus.objects.bulk_create(
                    store_statuses_to_create, batch_size=1000
                )

        logger.info(
            f"Successfully loaded {len(store_statuses_to_create)} store status records"
        )
        return len(store_statuses_to_create)

    except Exception as e:
        logger.error(
            f"Error loading store status chunk {chunk_start}-{chunk_start + chunk_size}: {e}"
        )
        raise


@shared_task
def load_business_hours_task():
    """
    Load business hours data (usually smaller dataset).
    """
    logger = get_task_logger(__name__)
    logger.info("Loading business hours data")

    try:
        base_data_path = settings.BASE_DIR.parent / "docs"
        business_hours_csv = base_data_path / "menu_hours.csv"

        business_hours_to_create = []

        with open(business_hours_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 1):
                try:
                    business_hours_to_create.append(
                        BusinessHours(
                            store_id=row["store_id"],
                            day_of_week=int(row["day"]),
                            start_time_local=datetime.strptime(
                                row["start_time_local"], "%H:%M:%S"
                            ).time(),
                            end_time_local=datetime.strptime(
                                row["end_time_local"], "%H:%M:%S"
                            ).time(),
                        )
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(
                        f"Skipping business hours row {row_num} due to error: {row} - {e}"
                    )

        with transaction.atomic():
            BusinessHours.objects.bulk_create(
                business_hours_to_create, batch_size=1000, ignore_conflicts=True
            )

        logger.info(
            f"Successfully loaded {len(business_hours_to_create)} business hours records"
        )
        return len(business_hours_to_create)

    except Exception as e:
        logger.error(f"Error loading business hours: {e}")
        raise


@shared_task
def load_timezones_task():
    """
    Load timezones data (usually smaller dataset).
    """
    logger = get_task_logger(__name__)
    logger.info("Loading timezones data")

    try:
        base_data_path = settings.BASE_DIR.parent / "docs"
        timezones_csv = base_data_path / "timezones.csv"

        timezones_to_create = []

        with open(timezones_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 1):
                try:
                    timezones_to_create.append(
                        StoreTimezone(
                            store_id=row["store_id"],
                            timezone_str=row.get("timezone_str", "America/Chicago"),
                        )
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(
                        f"Skipping timezone row {row_num} due to error: {row} - {e}"
                    )

        with transaction.atomic():
            StoreTimezone.objects.bulk_create(
                timezones_to_create, batch_size=500, ignore_conflicts=True
            )

        logger.info(f"Successfully loaded {len(timezones_to_create)} timezone records")
        return len(timezones_to_create)

    except Exception as e:
        logger.error(f"Error loading timezones: {e}")
        raise


@shared_task
def finalize_data_loading(results):
    """
    Finalize data loading after all chunks are complete.
    """
    logger = get_task_logger(__name__)

    # results will be a list containing:
    # [store_status_chunk_results, business_hours_count, timezones_count]
    store_status_results = results[0]  # List of counts from each chunk
    business_hours_count = results[1] if len(results) > 1 else 0
    timezones_count = results[2] if len(results) > 2 else 0

    total_store_status = (
        sum(store_status_results)
        if isinstance(store_status_results, list)
        else store_status_results
    )

    logger.info(f"Data loading completed!")
    logger.info(f"Store Status records: {total_store_status}")
    logger.info(f"Business Hours records: {business_hours_count}")
    logger.info(f"Timezone records: {timezones_count}")

    return {
        "store_status_count": total_store_status,
        "business_hours_count": business_hours_count,
        "timezones_count": timezones_count,
        "status": "completed",
    }

@shared_task
def load_csv_data_parallel_task(chunk_size: int = 10000):
    """
    Load CSV data using parallel processing.
    """
    logger = get_task_logger(__name__)
    logger.info(f"Starting parallel CSV data loading with chunk size: {chunk_size}")

    try:
        # First, clear existing store status data
        with transaction.atomic():
            StoreStatus.objects.all().delete()
            BusinessHours.objects.all().delete()
            StoreTimezone.objects.all().delete()
            logger.info(
                "Cleared existing store status, business hours and timezone data"
            )

        # Count total rows in store status file to determine chunks
        base_data_path = settings.BASE_DIR.parent / "docs"
        store_status_csv = base_data_path / "store_status.csv"

        total_rows = 0
        with open(store_status_csv, "r", encoding="utf-8") as f:
            total_rows = sum(1 for _ in f) - 1  # Subtract header row

        logger.info(f"Total store status rows to process: {total_rows}")

        # Create chunks for store status data
        store_status_chunks = []
        for start in range(0, total_rows, chunk_size):
            store_status_chunks.append(
                load_store_status_chunk_task.s(  # type:ignore
                    start, min(chunk_size, total_rows - start)
                )
            )

        logger.info(f"Created {len(store_status_chunks)} chunks for store status data")

        # Create chord: parallel store status loading + business hours + timezones
        job = chord(
            [
                group(store_status_chunks),  # Parallel store status chunks
                load_business_hours_task.s(),  # type:ignore Business hours
                load_timezones_task.s(),  # type:ignore Timezones
            ]
        )(
            finalize_data_loading.s()  # type:ignore
        )  # Finalize loading

        logger.info("Dispatched parallel data loading job")
        return f"Parallel data loading started with {len(store_status_chunks)} chunks"

    except Exception as e:
        logger.error(f"Error starting parallel data loading: {e}")
        raise
