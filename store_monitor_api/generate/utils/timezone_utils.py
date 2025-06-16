from celery.utils.log import get_task_logger
import pandas as pd
import pytz

logger = get_task_logger(__name__)


def _determine_store_timezone(
    store_id: str, timezones_df: pd.DataFrame
) -> pytz.BaseTzInfo:
    """Determines the timezone for a given store_id."""
    if timezones_df.empty:
        logger.error(
            f"Timezones DataFrame is empty. Cannot determine timezone for store {store_id}. Defaulting to America/Chicago."
        )
        return pytz.timezone("America/Chicago")

    # Log columns for debugging if store_id is not found
    if "store_id" not in timezones_df.columns:
        logger.error(
            f"Column 'store_id' not found in timezones_df. Columns: {timezones_df.columns.tolist()}. Defaulting to America/Chicago for store {store_id}."
        )
        return pytz.timezone("America/Chicago")

    store_tz_str_series = timezones_df[timezones_df["store_id"] == store_id][
        "timezone_str"
    ]
    store_tz_str = (
        store_tz_str_series.iloc[0]
        if not store_tz_str_series.empty
        else "America/Chicago"  # Default timezone
    )
    return pytz.timezone(store_tz_str)
