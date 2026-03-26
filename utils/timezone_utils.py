from datetime import datetime
from datetime import time as time_type

import pytz

IST = pytz.timezone("Asia/Kolkata")
UTC = pytz.utc


def ist_input_to_utc(appointment_date: str, appointment_time: str) -> datetime:
    """Convert form input date/time in IST into an aware UTC datetime."""
    local_naive = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
    ist_time = IST.localize(local_naive)
    return ist_time.astimezone(UTC)


def combine_utc_datetime(appointment_date, appointment_time: time_type) -> datetime:
    """Build an aware UTC datetime from UTC date/time fields stored in DB."""
    return UTC.localize(datetime.combine(appointment_date, appointment_time))


def convert_to_ist(utc_dt: datetime) -> datetime:
    """Convert UTC datetime (aware or naive) into aware IST datetime."""
    if utc_dt.tzinfo is None:
        utc_dt = UTC.localize(utc_dt)
    else:
        utc_dt = utc_dt.astimezone(UTC)
    return utc_dt.astimezone(IST)


def format_appointment_ist(appointment_date, appointment_time: time_type) -> str:
    """Render a UTC date/time pair as user-facing IST label."""
    utc_dt = combine_utc_datetime(appointment_date, appointment_time)
    return convert_to_ist(utc_dt).strftime("%d %b %Y, %I:%M %p")


def format_appointment_ist_date(appointment_date, appointment_time: time_type) -> str:
    """Render only IST date text for a UTC appointment."""
    utc_dt = combine_utc_datetime(appointment_date, appointment_time)
    return convert_to_ist(utc_dt).strftime("%d %b %Y")


def format_appointment_ist_time(appointment_date, appointment_time: time_type) -> str:
    """Render only IST time text for a UTC appointment."""
    utc_dt = combine_utc_datetime(appointment_date, appointment_time)
    return convert_to_ist(utc_dt).strftime("%I:%M %p")
