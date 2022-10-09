from datetime import datetime

import pytz

TIMEZONE = pytz.timezone('Europe/Prague')


def localize_datetime(timestamp: datetime) -> datetime:
    return TIMEZONE.localize(timestamp)


def utcnow_localized() -> datetime:
    return localize_datetime(datetime.utcnow())
