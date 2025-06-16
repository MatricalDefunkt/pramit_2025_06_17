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
