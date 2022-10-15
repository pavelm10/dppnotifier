from datetime import datetime

import pytz

TIMEZONE = pytz.timezone('Europe/Prague')


def localize_datetime(timestamp: datetime) -> datetime:
    """Converts the timezone unaware datetime to zone aware.

    Parameters
    ----------
    timestamp : datetime
        Timezone unaware datetime

    Returns
    -------
    datetime
        Zone aware datetime
    """
    return TIMEZONE.localize(timestamp)


def utcnow_localized() -> datetime:
    """Gets current UTC time and converts it to the local time zone aware.

    Returns
    -------
    datetime
        Local UTC time zone aware
    """
    return localize_datetime(datetime.utcnow())
