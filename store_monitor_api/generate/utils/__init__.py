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

from .time_utils import get_current_utc_time
from .database_utils import _load_all_data
from .timezone_utils import _determine_store_timezone
from .business_hours_utils import _get_business_hour_segments_for_day_utc
from .metrics_utils import (
    _calculate_uptime_downtime_for_effective_segment,
    _calculate_metrics_for_period,
    _process_single_store_metrics,
)
from .report_utils import (
    process_store_chunk_task,
    combine_report_results,
    generate_report_parallel_task,
)
from .csv_utils import (
    load_store_status_chunk_task,
    load_business_hours_task,
    load_timezones_task,
    finalize_data_loading,
    load_csv_data_parallel_task,
)

__all__ = [
    "get_current_utc_time",
    "_load_all_data",
    "_determine_store_timezone",
    "_get_business_hour_segments_for_day_utc",
    "_calculate_uptime_downtime_for_effective_segment",
    "_calculate_metrics_for_period",
    "_process_single_store_metrics",
    "process_store_chunk_task",
    "combine_report_results",
    "generate_report_parallel_task",
    "load_store_status_chunk_task",
    "load_business_hours_task",
    "load_timezones_task",
    "finalize_data_loading",
    "load_csv_data_parallel_task",
]
