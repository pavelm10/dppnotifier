import logging
import os
from typing import Any, List, Optional, Tuple

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


def filter_subscriber(
    event: TrafficEvent, subscribers: List[Subscriber]
) -> Tuple[Subscriber]:
    subs = []
    for sub in subscribers:
        if len(sub.lines) == 0:
            subs.append(sub)
            continue
        if set(sub.lines).intersection(set(event.lines)):
            subs.append(sub)
    return tuple(subs)


def update_db(event: TrafficEvent, events_db: DynamoTrafficEventsDb):
    try:
        events_db.upsert_event(event)
    except (ValueError, IndexError, KeyError) as exc:
        _LOGGER.error('Failed to upsert the event - notification skipped')
        _LOGGER.error(exc)
        raise FailedUpsertEvent(event.event_id) from exc


def run_job(
    trigger_event: Optional[Any] = None, context: Optional[Any] = None
):
    init_logger()
    events_db = DynamoTrafficEventsDb(
        table_name=os.getenv('EVENTS_TABLE', 'dpp-notifier-events')
    )

    _LOGGER.info('Fetching current events')
    events = []
    db_events = []
    to_notify = False
    for event in fetch_events():
        db_event = events_db.find_by_id(event.event_id)
        events.append(event)
        db_events.append(db_event)
        if event.active and db_event is None:
            to_notify = True

    if not to_notify:
        _LOGGER.info('No new events - terminating')
        return

    subs_db = DynamoSubscribersDb(
        table_name=os.getenv('SUBSCRIBERS_TABLE', 'dpp-notifier-recepients')
    )
    notifiers = build_notifiers(subs_db)

    for event, db_event in zip(events, db_events):
        if event != db_event:
            try:
                update_db(event, events_db)
            except FailedUpsertEvent:
                continue

        if event.active and db_event is None:
            _LOGGER.info(event.to_log_message())
            notify(notifiers, event)

    _LOGGER.info('Job finished')


class FailedUpsertEvent(Exception):
    """Upsert to DynamoDB failed"""
