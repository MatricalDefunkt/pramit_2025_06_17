from datetime import datetime, timedelta
from typing import Dict, Tuple, Union
import pandas as pd  # Ensure pandas is imported
import pytz  # Ensure pytz is imported

from .business_hours_utils import _get_business_hour_segments_for_day_utc
from .timezone_utils import _determine_store_timezone


def _calculate_uptime_downtime_for_effective_segment(
    effective_interval_start: datetime,
    effective_interval_end: datetime,
    relevant_observations: pd.DataFrame,
    is_store_24_7: bool,  # True if daily_business_hours was empty
    store_id: str,
    logger,
) -> Tuple[float, float]:
    """
    Calculates uptime and downtime in milliseconds for a single effective business hour segment.
    """
    segment_uptime_ms = 0.0
    segment_downtime_ms = 0.0

    if relevant_observations.empty:
        duration_ms = (
            effective_interval_end - effective_interval_start
        ).total_seconds() * 1000
        if is_store_24_7:  # Store is 24/7 and no observations (or too old)
            logger.debug(
                f"    Store {store_id}: No relevant observations for 24/7 segment "
                f"{effective_interval_start} to {effective_interval_end}. Counting as downtime."
            )
            segment_downtime_ms += duration_ms  # Changed from uptime to downtime
        # If not is_store_24_7 and observations are empty, it implies this segment
        # is outside defined business hours or there's no BH data.
        # In this case, both uptime and downtime should remain 0 for this segment.
        return segment_uptime_ms, segment_downtime_ms

    current_segment_pointer_utc = effective_interval_start
    last_known_status = None

    # Determine status at the beginning of the effective_interval_start
    initial_status_obs = relevant_observations[
        relevant_observations["timestamp_utc"] <= effective_interval_start
    ].tail(1)

    if not initial_status_obs.empty:
        last_known_status = initial_status_obs["status"].iloc[0]
    else:
        # No observation before or at effective_interval_start (that meets the 8-day rule if applicable further up)
        last_known_status = None

    logger.debug(
        f"    Initial status for effective segment: {last_known_status} starting at {current_segment_pointer_utc}"
    )

    # Iterate through observations that fall *within or at the end of* the effective business hour segment
    for _, obs_row in relevant_observations[
        (relevant_observations["timestamp_utc"] >= effective_interval_start)
        & (relevant_observations["timestamp_utc"] <= effective_interval_end)
    ].iterrows():
        obs_time_utc = obs_row["timestamp_utc"]
        obs_status = obs_row["status"]

        if obs_time_utc > current_segment_pointer_utc:  # Ensure time has advanced
            # If status has changed, split the interval at the midpoint
            if last_known_status is not None and last_known_status != obs_status:
                midpoint_utc = (
                    current_segment_pointer_utc
                    + (obs_time_utc - current_segment_pointer_utc) / 2
                )

                # First half of interval has the last known status
                duration_first_half_ms = (
                    midpoint_utc - current_segment_pointer_utc
                ).total_seconds() * 1000
                if last_known_status == "active":
                    segment_uptime_ms += duration_first_half_ms
                    logger.debug(
                        f"      + {duration_first_half_ms/1000:.2f}s uptime (status: {last_known_status}) from {current_segment_pointer_utc} to {midpoint_utc}"
                    )
                else:  # inactive
                    segment_downtime_ms += duration_first_half_ms
                    logger.debug(
                        f"      + {duration_first_half_ms/1000:.2f}s downtime (status: {last_known_status}) from {current_segment_pointer_utc} to {midpoint_utc}"
                    )

                # Second half of interval has the new observation's status
                duration_second_half_ms = (
                    obs_time_utc - midpoint_utc
                ).total_seconds() * 1000
                if obs_status == "active":
                    segment_uptime_ms += duration_second_half_ms
                    logger.debug(
                        f"      + {duration_second_half_ms/1000:.2f}s uptime (status: {obs_status}) from {midpoint_utc} to {obs_time_utc}"
                    )
                else:  # inactive
                    segment_downtime_ms += duration_second_half_ms
                    logger.debug(
                        f"      + {duration_second_half_ms/1000:.2f}s downtime (status: {obs_status}) from {midpoint_utc} to {obs_time_utc}"
                    )
            else:
                # Status is the same, or this is the first observation in the segment.
                # The whole interval gets the same status.
                duration_ms = (
                    obs_time_utc - current_segment_pointer_utc
                ).total_seconds() * 1000
                status_for_interval = (
                    last_known_status if last_known_status is not None else obs_status
                )
                if status_for_interval == "active":
                    segment_uptime_ms += duration_ms
                    logger.debug(
                        f"      + {duration_ms/1000:.2f}s uptime (status: {status_for_interval}) from {current_segment_pointer_utc} to {obs_time_utc}"
                    )
                elif status_for_interval == "inactive":
                    segment_downtime_ms += duration_ms
                    logger.debug(
                        f"      + {duration_ms/1000:.2f}s downtime (status: {status_for_interval}) from {current_segment_pointer_utc} to {obs_time_utc}"
                    )

        current_segment_pointer_utc = obs_time_utc
        last_known_status = obs_status

    # Account for time from the last observation to the end of the segment
    if current_segment_pointer_utc < effective_interval_end:
        duration_ms = (
            effective_interval_end - current_segment_pointer_utc
        ).total_seconds() * 1000
        if last_known_status == "active":
            segment_uptime_ms += duration_ms
        else:  # Covers "inactive" or None
            segment_downtime_ms += duration_ms

    return segment_uptime_ms, segment_downtime_ms


def _calculate_metrics_for_period(
    period_start_utc: datetime,
    period_end_utc: datetime,
    store_id: str,
    store_data: pd.DataFrame,  # Observations for this store only
    store_business_hours: pd.DataFrame,  # Business hours for this store only
    store_timezone: pytz.BaseTzInfo,
    logger,
    current_report_time_utc: datetime,  # New parameter for the 8-day rule
) -> Tuple[float, float]:
    """
    Calculates total uptime and downtime in milliseconds for a store over a given period (e.g., last_hour, last_day).
    """
    total_period_uptime_ms = 0.0
    total_period_downtime_ms = 0.0

    # Filter observations relevant to the period (including one before and one after)
    period_observations = store_data[
        (store_data["timestamp_utc"] >= period_start_utc)
        & (store_data["timestamp_utc"] <= period_end_utc)
    ]
    obs_before_period = store_data[store_data["timestamp_utc"] < period_start_utc].tail(
        1
    )
    obs_after_period = store_data[store_data["timestamp_utc"] > period_end_utc].head(1)

    # Apply 8-day rule: If the last observation before the period is too old, discard it.
    if not obs_before_period.empty:
        last_obs_timestamp = obs_before_period["timestamp_utc"].iloc[0]
        # Ensure timestamps are comparable (current_report_time_utc is UTC, last_obs_timestamp should be UTC)
        if pd.Timestamp(current_report_time_utc) - pd.Timestamp(
            last_obs_timestamp
        ) > timedelta(
            days=8
        ):  # Changed 3 to 8
            logger.debug(
                f"    Store {store_id}: Discarding obs_before_period (timestamp {last_obs_timestamp}) "
                f"as it's older than 8 days from report time {current_report_time_utc} for period starting {period_start_utc}."  # Updated log message
            )
            obs_before_period = pd.DataFrame()  # Empty it, so it's not used

    relevant_observations = (
        pd.concat([obs_before_period, period_observations, obs_after_period])
        .drop_duplicates()
        .sort_values(by="timestamp_utc")
    )

    current_day_processing_utc = period_start_utc.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    while current_day_processing_utc <= period_end_utc:
        day_of_week = current_day_processing_utc.weekday()

        daily_store_business_hours = store_business_hours[
            store_business_hours["day_of_week"] == day_of_week
        ]
        is_store_24_7_this_day = daily_store_business_hours.empty

        bh_segments_utc_for_day = _get_business_hour_segments_for_day_utc(
            current_day_processing_utc,
            daily_store_business_hours,
            store_timezone,
            logger,
        )

        for bh_start_utc, bh_end_utc in bh_segments_utc_for_day:
            effective_interval_start = max(period_start_utc, bh_start_utc)
            effective_interval_end = min(period_end_utc, bh_end_utc)

            if effective_interval_start >= effective_interval_end:
                continue

            logger.debug(
                f"  Store {store_id}, Day {day_of_week}, BH UTC: {bh_start_utc} - {bh_end_utc}, Effective UTC: {effective_interval_start} - {effective_interval_end}"
            )

            segment_uptime_ms, segment_downtime_ms = (
                _calculate_uptime_downtime_for_effective_segment(
                    effective_interval_start,
                    effective_interval_end,
                    relevant_observations,  # Pass all relevant observations for the period
                    is_store_24_7_this_day,
                    store_id,
                    logger,
                )
            )
            total_period_uptime_ms += segment_uptime_ms
            total_period_downtime_ms += segment_downtime_ms

        current_day_processing_utc += timedelta(days=1)

    return total_period_uptime_ms, total_period_downtime_ms


def _process_single_store_metrics(
    store_id: str,
    store_statuses_df: pd.DataFrame,  # All store statuses
    business_hours_df: pd.DataFrame,  # All business hours
    timezones_df: pd.DataFrame,  # All timezones
    current_time_utc: datetime,  # This is the overall report generation time
    cache,  # Django cache instance
    logger,
) -> str:
    """
    Processes a single store to calculate its uptime/downtime metrics and returns a report line.
    """
    logger.info(f"Processing store_id: {store_id}")

    # Check if DataFrames have required columns
    if not store_statuses_df.empty and "store_id" not in store_statuses_df.columns:
        logger.error(
            f"store_statuses_df missing 'store_id' column. Available columns: {store_statuses_df.columns.tolist()}"
        )
        raise KeyError("store_id column not found in store_statuses_df")

    if not business_hours_df.empty and "store_id" not in business_hours_df.columns:
        logger.error(
            f"business_hours_df missing 'store_id' column. Available columns: {business_hours_df.columns.tolist()}"
        )
        raise KeyError("store_id column not found in business_hours_df")

    store_timezone = _determine_store_timezone(store_id, timezones_df)

    # Filter data for the current store
    store_data = (
        store_statuses_df[store_statuses_df["store_id"] == store_id].sort_values(
            by="timestamp_utc"
        )
        if not store_statuses_df.empty
        else pd.DataFrame()
    )

    store_business_hours = (
        business_hours_df[business_hours_df["store_id"] == store_id]
        if not business_hours_df.empty
        else pd.DataFrame()
    )

    one_hour_ago = current_time_utc - timedelta(hours=1)
    one_day_ago = current_time_utc - timedelta(days=1)
    one_week_ago = current_time_utc - timedelta(weeks=1)

    intervals: Dict[str, Tuple[datetime, datetime]] = {
        "last_hour": (one_hour_ago, current_time_utc),
        "last_day": (one_day_ago, current_time_utc),
        "last_week": (one_week_ago, current_time_utc),
    }

    results: Dict[str, Union[int, float]] = {
        "uptime_last_hour": 0,
        "downtime_last_hour": 0,
        "uptime_last_day": 0.0,
        "downtime_last_day": 0.0,
        "uptime_last_week": 0.0,
        "downtime_last_week": 0.0,
    }

    for period_name, (start_utc, end_utc) in intervals.items():
        logger.debug(
            f"Calculating for period {period_name} ({start_utc} to {end_utc}) for store {store_id}"
        )
        period_uptime_ms, period_downtime_ms = _calculate_metrics_for_period(
            start_utc,
            end_utc,
            store_id,
            store_data,
            store_business_hours,
            store_timezone,
            logger,
            current_time_utc,  # Pass current_time_utc for the 8-day rule
        )

        if period_name == "last_hour":
            results["uptime_last_hour"] = round(
                period_uptime_ms / (1000 * 60)
            )  # minutes
            results["downtime_last_hour"] = round(
                period_downtime_ms / (1000 * 60)
            )  # minutes
        else:
            results[f"uptime_{period_name}"] = round(
                period_uptime_ms / (1000 * 60 * 60), 2
            )  # hours
            results[f"downtime_{period_name}"] = round(
                period_downtime_ms / (1000 * 60 * 60), 2
            )  # hours

    report_line = f"{store_id},{results['uptime_last_hour']},{results['uptime_last_day']},{results['uptime_last_week']},{results['downtime_last_hour']},{results['downtime_last_day']},{results['downtime_last_week']}"
    logger.info(f"Finished processing store_id: {store_id}. Results: {report_line}")
    return report_line
