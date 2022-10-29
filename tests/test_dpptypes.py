from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from dppnotifier.app.dpptypes import Notifiers, Subscriber, TrafficEvent

EVENT_A = TrafficEvent(
    active=True,
    lines=['A', '7', 'S3', '136', '16'],
    message='message',
    event_id='eidA',
    url='url',
)

BASE_DAY = datetime(2022, 10, 24)
DAYS = tuple([BASE_DAY + timedelta(days=idx) for idx in range(7)])
HOURS = tuple([timedelta(hours=idx) for idx in range(24)])
DAY_MASK = (True, False, True, True, False, False, False)
HOUR_MASK = (
    False,
    False,
    False,
    False,
    False,
    False,
    False,
    True,
    True,
    True,
    False,
    False,
    False,
    False,
    False,
    False,
    True,
    True,
    True,
    True,
    False,
    False,
    False,
    False,
)


@pytest.mark.parametrize(
    'sub, expected',
    (
        (
            (
                Subscriber(
                    notifier=Notifiers.AWS_SES,
                    uri='all',
                    user='user',
                    lines=(),
                ),
                True,
            ),
            (
                Subscriber(
                    notifier=Notifiers.AWS_SES,
                    uri='none',
                    user='user',
                    lines=('B',),
                ),
                False,
            ),
            (
                Subscriber(
                    notifier=Notifiers.AWS_SES,
                    uri='A7',
                    user='user',
                    lines=('A', '7'),
                ),
                True,
            ),
            (
                Subscriber(
                    notifier=Notifiers.AWS_SES,
                    uri='136',
                    user='user',
                    lines=('9', '136'),
                ),
                True,
            ),
        )
    ),
)
def test_filter_subscriber_by_line(sub, expected):
    out = sub.is_interested(EVENT_A)
    assert out == expected


@pytest.mark.parametrize('day_index', tuple(range(7)))
@pytest.mark.parametrize('hour_index', tuple(range(24)))
def test_filter_subscriber_by_time(day_index, hour_index):
    sub = Subscriber(
        notifier=Notifiers.AWS_SES,
        uri='all',
        user='user',
        lines=(),
        time_filter_expression=(
            1,
            0,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
        ),
    )

    event = deepcopy(EVENT_A)
    event.start_date = DAYS[day_index] + HOURS[hour_index]
    expected = DAY_MASK[day_index] and HOUR_MASK[hour_index]
    out = sub.is_interested(event)
    assert out == expected
