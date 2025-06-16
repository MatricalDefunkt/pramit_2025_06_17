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

from datetime import datetime
import pytz
from django.conf import settings
from django.utils.dateparse import parse_datetime


def get_current_utc_time():
    override_timestamp_str = getattr(settings, "CURRENT_TIMESTAMP_OVERRIDE", None)
    if override_timestamp_str:
        try:
            # Attempt to parse the timestamp.
            # Ensure it's an ISO format string e.g., "2023-10-26T10:00:00Z" or "2023-10-26 10:00:00+00:00"
            dt = parse_datetime(override_timestamp_str)
            if dt:
                if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                    # If naive, assume UTC, then localize
                    dt = pytz.utc.localize(dt)
                else:
                    # If aware, convert to UTC
                    dt = dt.astimezone(pytz.utc)
                return dt
            # Fallback if parse_datetime returns None (invalid format)
        except Exception:
            # Log an error or warning here if you have a logger available
            # For now, falling back to current time
            pass  # Fall through to default
    return datetime.now(pytz.utc)
