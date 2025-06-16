from django.core.management.base import BaseCommand, CommandError
from store_monitor_api.models import StoreStatus, BusinessHours, StoreTimezone
from django.conf import settings
import pandas as pd
import csv
from datetime import datetime, time
from django.db import transaction
import pytz  # For timezone handling in pd.to_datetime


class Command(BaseCommand):
    help = "Loads data from CSV files into the database"

    def handle(self, *args, **options):
        base_data_path = settings.BASE_DIR.parent / "docs"  # Corrected path

        store_status_csv = base_data_path / "store_status.csv"
        business_hours_csv = base_data_path / "menu_hours.csv"
        timezones_csv = base_data_path / "timezones.csv"

        self.stdout.write(f"Base data path: {base_data_path}")
        self.stdout.write(f"Store status CSV path: {store_status_csv}")
        self.stdout.write(f"Business hours CSV path: {business_hours_csv}")
        self.stdout.write(f"Timezones CSV path: {timezones_csv}")

        # Load Store Status Data
        try:
            self.stdout.write(f"Loading store statuses from {store_status_csv}...")
            store_statuses_to_create = []
            with open(store_status_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, 1):
                    try:
                        store_id = row["store_id"]  # Changed: store_id is CharField
                        # Pandas to_datetime is robust for various formats and handles UTC correctly
                        # The problem states "All timestamps are in UTC"
                        timestamp_str = row["timestamp_utc"]
                        # Try to parse with common formats, then fallback or error
                        try:
                            # Format: 2023-01-24 10:00:00.123456 UTC
                            dt_obj = datetime.strptime(
                                timestamp_str.replace(" UTC", ""),
                                "%Y-%m-%d %H:%M:%S.%f",
                            )
                        except ValueError:
                            try:
                                # Format: 2023-01-24 10:00:00 UTC
                                dt_obj = datetime.strptime(
                                    timestamp_str.replace(" UTC", ""),
                                    "%Y-%m-%d %H:%M:%S",
                                )
                            except ValueError as e_parse:
                                self.stderr.write(
                                    self.style.WARNING(
                                        f"Row {row_num}: Could not parse timestamp '{timestamp_str}' for store {store_id}. Error: {e_parse}. Skipping row."
                                    )
                                )
                                continue

                        ts_utc = pytz.utc.localize(dt_obj)
                        status = row["status"]
                        # Accessing choices directly from the field instance
                        if status not in [
                            "active",
                            "inactive",
                        ]:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Row {row_num}: Invalid status '{status}' for store {store_id}. Skipping row."
                                )
                            )
                            continue

                        store_statuses_to_create.append(
                            StoreStatus(
                                store_id=store_id, timestamp_utc=ts_utc, status=status
                            )
                        )
                    except KeyError as ke:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Row {row_num}: Missing expected column: {ke}. Skipping row: {row}"
                            )
                        )
                        continue
                    except (
                        ValueError
                    ) as ve:  # Catch potential errors from int() if store_id was not a string
                        self.stderr.write(
                            self.style.WARNING(
                                f"Row {row_num}: Error processing row: {ve}. Skipping row: {row}"
                            )
                        )
                        continue

            with transaction.atomic():
                StoreStatus.objects.all().delete()  # Clear existing data
                StoreStatus.objects.bulk_create(
                    store_statuses_to_create, batch_size=1000
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully loaded {len(store_statuses_to_create)} store statuses"
                )
            )
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {store_status_csv}"))
            # raise CommandError(f"File not found: {store_status_csv}") # Optionally stop execution
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error loading store statuses: {e}"))
            # raise CommandError(f'Error loading store statuses: {e}')

        # Load Business Hours Data
        try:
            self.stdout.write(f"Loading business hours from {business_hours_csv}...")
            business_hours_to_create = []
            with open(business_hours_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, 1):
                    try:
                        store_id = row["store_id"]  # Changed: store_id is CharField
                        day_of_week = int(row["dayOfWeek"])
                        if not (0 <= day_of_week <= 6):
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Row {row_num}: Invalid dayOfWeek '{day_of_week}' for store {store_id}. Skipping row."
                                )
                            )
                            continue

                        start_time_local = datetime.strptime(
                            row["start_time_local"], "%H:%M:%S"
                        ).time()
                        end_time_local = datetime.strptime(
                            row["end_time_local"], "%H:%M:%S"
                        ).time()

                        business_hours_to_create.append(
                            BusinessHours(
                                store_id=store_id,
                                day_of_week=day_of_week,
                                start_time_local=start_time_local,
                                end_time_local=end_time_local,
                            )
                        )
                    except KeyError as ke:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Row {row_num}: Missing expected column in business hours: {ke}. Skipping row: {row}"
                            )
                        )
                        continue
                    except (
                        ValueError
                    ) as ve:  # Catch potential errors from int() if store_id was not a string
                        self.stderr.write(
                            self.style.WARNING(
                                f"Row {row_num}: Error processing business hours row: {ve}. Skipping row: {row}"
                            )
                        )
                        continue

            with transaction.atomic():
                BusinessHours.objects.all().delete()
                # Use ignore_conflicts=True because of the unique_together constraint in the model
                BusinessHours.objects.bulk_create(
                    business_hours_to_create, batch_size=1000, ignore_conflicts=True
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully loaded {len(business_hours_to_create)} business hours records"
                )
            )
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {business_hours_csv}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error loading business hours: {e}"))

        # Load Timezones Data
        try:
            self.stdout.write(f"Loading timezones from {timezones_csv}...")
            timezones_to_update_or_create = []
            with open(timezones_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, 1):
                    try:
                        store_id = row["store_id"]  # Changed: store_id is CharField
                        timezone_str = row["timezone_str"]
                        if not timezone_str:  # If timezone_str is empty, use default
                            timezone_str = "America/Chicago"  # Default from model
                        # Validate timezone string if possible (pytz.timezone(timezone_str) would do this)
                        try:
                            pytz.timezone(timezone_str)
                        except pytz.exceptions.UnknownTimeZoneError:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Row {row_num}: Unknown timezone '{timezone_str}' for store {store_id}. Using default 'America/Chicago'."
                                )
                            )
                            timezone_str = "America/Chicago"  # Default from model

                        timezones_to_update_or_create.append(
                            {"store_id": store_id, "timezone_str": timezone_str}
                        )
                    except KeyError as ke:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Row {row_num}: Missing expected column in timezones: {ke}. Skipping row: {row}"
                            )
                        )
                        continue
                    except (
                        ValueError
                    ) as ve:  # Catch potential errors from int() if store_id was not a string
                        self.stderr.write(
                            self.style.WARNING(
                                f"Row {row_num}: Error processing timezones row: {ve}. Skipping row: {row}"
                            )
                        )
                        continue

            with transaction.atomic():
                # StoreTimezone has store_id as primary key. We can't bulk_create with ignore_conflicts easily for updates.
                # So, we delete and then bulk_create, or iterate with update_or_create.
                # Given the small size of timezone data typically, update_or_create is fine.
                StoreTimezone.objects.all().delete()  # Clear first for simplicity with bulk_create
                StoreTimezone.objects.bulk_create(
                    [
                        StoreTimezone(
                            store_id=data["store_id"], timezone_str=data["timezone_str"]
                        )
                        for data in timezones_to_update_or_create
                    ],
                    batch_size=500,
                    ignore_conflicts=True,
                )  # store_id is PK, so ignore_conflicts handles existing.

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully loaded/updated {len(timezones_to_update_or_create)} timezones"
                )
            )
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {timezones_csv}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error loading timezones: {e}"))

        self.stdout.write(self.style.SUCCESS("Data loading process finished."))
