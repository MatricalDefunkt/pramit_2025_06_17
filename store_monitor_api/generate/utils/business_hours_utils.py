from datetime import datetime, timedelta, time
from typing import List, Tuple
import pandas as pd
import pytz


def _get_business_hour_segments_for_day_utc(
    current_day_processing_utc: datetime,
    daily_store_business_hours: pd.DataFrame,
    store_timezone: pytz.BaseTzInfo,  # Corrected type hint
    logger,
) -> List[Tuple[datetime, datetime]]:
    """
    Calculates UTC business hour segments for a given day and store.
    """
    bh_segments_utc_for_day: List[Tuple[datetime, datetime]] = []
    local_date_for_bh = current_day_processing_utc.astimezone(store_timezone).date()

    if daily_store_business_hours.empty:  # Assume 24/7
        local_day_start = datetime.combine(local_date_for_bh, time.min)
        local_day_end = datetime.combine(local_date_for_bh, time.max)

        bh_start_utc_candidate = store_timezone.localize(local_day_start).astimezone(
            pytz.utc
        )
        bh_end_utc_candidate = store_timezone.localize(local_day_end).astimezone(
            pytz.utc
        )
        bh_segments_utc_for_day.append((bh_start_utc_candidate, bh_end_utc_candidate))
    else:
        for _, row in daily_store_business_hours.iterrows():
            start_local_dt_naive = datetime.combine(
                local_date_for_bh, row["start_time_local"]
            )
            end_local_dt_naive = datetime.combine(
                local_date_for_bh, row["end_time_local"]
            )

            if end_local_dt_naive <= start_local_dt_naive:  # Handles overnight
                end_local_dt_for_conversion = datetime.combine(
                    local_date_for_bh + timedelta(days=1),
                    row["end_time_local"],
                )
            else:
                end_local_dt_for_conversion = end_local_dt_naive

            try:
                bh_start_utc_candidate = store_timezone.localize(
                    start_local_dt_naive
                ).astimezone(pytz.utc)
                bh_end_utc_candidate = store_timezone.localize(
                    end_local_dt_for_conversion
                ).astimezone(pytz.utc)
                bh_segments_utc_for_day.append(
                    (bh_start_utc_candidate, bh_end_utc_candidate)
                )
            except pytz.exceptions.AmbiguousTimeError as e:
                logger.warning(
                    f"Ambiguous time for store, date {local_date_for_bh}, start {row['start_time_local']}: {e}"
                )
                # Handle by possibly trying is_dst=True/False or skipping
            except pytz.exceptions.NonExistentTimeError as e:
                logger.warning(
                    f"Non-existent time for store, date {local_date_for_bh}, start {row['start_time_local']}: {e}"
                )
                # Handle by possibly adjusting or skipping

    return bh_segments_utc_for_day
