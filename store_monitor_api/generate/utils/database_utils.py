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
from store_monitor_api.models import StoreStatus, BusinessHours, StoreTimezone
from typing import Tuple

logger = get_task_logger(__name__)


def _load_all_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads all necessary data from the database into pandas DataFrames."""
    logger.info("Loading data from DB...")

    # Load data with debugging
    store_statuses_data = list(StoreStatus.objects.all().values())
    business_hours_data = list(BusinessHours.objects.all().values())
    timezones_data = list(
        StoreTimezone.objects.all().values("store_id", "timezone_str")
    )

    logger.info(f"Store statuses count: {len(store_statuses_data)}")
    logger.info(f"Business hours count: {len(business_hours_data)}")
    logger.info(f"Timezones count: {len(timezones_data)}")

    # Create DataFrames
    store_statuses_df = pd.DataFrame(store_statuses_data)
    business_hours_df = pd.DataFrame(business_hours_data)
    timezones_df = pd.DataFrame(timezones_data)

    # Debug column names
    if not store_statuses_df.empty:
        logger.info(f"Store statuses columns: {store_statuses_df.columns.tolist()}")
    else:
        logger.warning("Store statuses DataFrame is empty")

    if not business_hours_df.empty:
        logger.info(f"Business hours columns: {business_hours_df.columns.tolist()}")
    else:
        logger.warning("Business hours DataFrame is empty")

    if not timezones_df.empty:
        logger.info(f"Timezones columns: {timezones_df.columns.tolist()}")
    else:
        logger.warning("Timezones DataFrame is empty")

    logger.info("Data loading complete.")
    return store_statuses_df, business_hours_df, timezones_df
