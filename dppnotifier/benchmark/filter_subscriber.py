import functools
import time
from random import randint
from statistics import mean, stdev

from dppnotifier.app.app import filter_subscriber
from dppnotifier.app.dpptypes import Notifiers, Subscriber, TrafficEvent
from dppnotifier.app.utils import utcnow_localized

EVENT_A = TrafficEvent(
    active=True,
    lines=['17'],
    message='a message',
    event_id='1234',
    url='url-1234',
    start_date=utcnow_localized(),
)

EVENT_B = TrafficEvent(
    active=True,
    lines=['17', '1', '7', '19'],
    message='a message',
    event_id='1235',
    url='url-1235',
    start_date=utcnow_localized(),
)

EVENT_C = TrafficEvent(
    active=True,
    lines=[str(el) for el in range(1, 28)],
    message='a message',
    event_id='1236',
    url='url-1236',
    start_date=utcnow_localized(),
)


def check_performance(func):
    durations = []

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for _ in range(20):
            start_time = time.perf_counter()
            func(*args, **kwargs)
            durations.append(time.perf_counter() - start_time)
        print(
            f'Mean duration: {mean(durations):.3f} +/- {stdev(durations):.3f}'
            ' seconds'
        )

    return wrapper


def subscriber_factory(lines):
    return Subscriber(
        notifier=Notifiers.AWS_SES,
        uri='email@email.com',
        user='some user',
        lines=lines,
    )


@check_performance
def run_filter(event, subscribers):
    filter_subscriber(event, subscribers)


def bench_for_events(subscribers: int):
    for event in [EVENT_A, EVENT_B, EVENT_C]:
        print(f'Starting for event with lines {event.lines}')
        run_filter(event, subscribers)


def main():
    subs = [
        subscriber_factory([randint(1, 36) for _ in range(10)])
        for _ in range(int(1e6))
    ]
    print('1M subs 10 lines filter')
    bench_for_events(subs)


if __name__ == '__main__':
    main()
