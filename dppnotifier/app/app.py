import logging
import os
from typing import List, Tuple

from dppnotifier.app.db import DynamoSubscribersDb, DynamoTrafficEventsDb
from dppnotifier.app.log import init_logger
from dppnotifier.app.notifier import (
    AwsSesNotifier,
    TelegramNotifier,
    WhatsAppNotifier,
)
from dppnotifier.app.scrapper import TrafficEvent, fetch_events
from dppnotifier.app.types import NotifierSubscribers, Subscriber

_LOGGER = logging.getLogger(__name__)


def build_notifiers(
    subscribers_db: DynamoSubscribersDb,
) -> List[NotifierSubscribers]:
    possible_notifiers = (AwsSesNotifier, TelegramNotifier, WhatsAppNotifier)
    notifiers = []
    for notifier_class in possible_notifiers:
        subscribers = subscribers_db.get_subscriber(
            notifier_type=notifier_class.NOTIFIER_TYPE
        )
        if len(subscribers) > 0:
            notifier = notifier_class()
            if notifier.enabled:
                notifiers.append(
                    NotifierSubscribers(
                        notifier=notifier,
                        subscribers=subscribers,
                    )
                )
                _LOGGER.info(
                    '%s notifier registered', notifier.NOTIFIER_TYPE.value
                )

    _LOGGER.info('Notifiers and subscribers set up')
    return notifiers


def notify(notifiers: List[NotifierSubscribers], event: TrafficEvent):
    for notifier_subscribers in notifiers:
        subs = filter_subscriber(event, notifier_subscribers.subscribers)
        if len(subs) > 0:
            notifier_subscribers.notifier.notify(event, subs)


def log_event(event: TrafficEvent):
    _LOGGER.info('Started %s, URL: %s', event.start_date, event.url)


def filter_subscriber(
    event: TrafficEvent, subscribers: List[Subscriber]
) -> Tuple[Subscriber]:
    subs = []
    for sub in subscribers:
        if set(sub.lines).issubset(set(event.lines)):
            subs.append(sub)
    return tuple(subs)


def main():
    init_logger()
    events_db = DynamoTrafficEventsDb(
        table_name=os.getenv('EVENTS_TABLE', 'dpp-notifier-events')
    )
    subs_db = DynamoSubscribersDb(
        table_name=os.getenv('SUBSCRIBERS_TABLE', 'dpp-notifier-recepients')
    )
    notifiers = build_notifiers(subs_db)

    _LOGGER.info('Fetching current events')
    for event in fetch_events():
        log_event(event)
        db_event = events_db.find_by_id(event.event_id)

        try:
            events_db.upsert_event(event)
        except (ValueError, IndexError, KeyError) as exc:
            _LOGGER.error('Failed to upsert the event - notification skipped')
            _LOGGER.error(exc)
            continue

        if event.active and db_event is None:
            notify(notifiers, event)


if __name__ == '__main__':
    main()
