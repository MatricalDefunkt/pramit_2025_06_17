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
