from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo('Asia/Shanghai')


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _aware_utc(value):
    if value is None:
        value = utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def week_start_for(now_utc=None):
    local = _aware_utc(now_utc).astimezone(SHANGHAI)
    return local.date() - timedelta(days=local.weekday())


def week_end_utc(week_start):
    local_end = datetime.combine(week_start + timedelta(days=7), time.min, SHANGHAI)
    return local_end.astimezone(timezone.utc).replace(tzinfo=None)


def parse_shanghai_datetime(value):
    local = datetime.fromisoformat(value)
    if local.tzinfo is None:
        local = local.replace(tzinfo=SHANGHAI)
    else:
        local = local.astimezone(SHANGHAI)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def to_shanghai_iso(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(SHANGHAI).isoformat(timespec='seconds')
