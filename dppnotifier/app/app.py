import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from dppnotifier.app.db import DynamoSubscribersDb, DynamoTrafficEventsDb
from dppnotifier.app.dpptypes import NotifierSubscribers, Subscriber
from dppnotifier.app.log import init_logger
from dppnotifier.app.notifier import (
    AwsSesNotifier,
    TelegramNotifier,
    WhatsAppNotifier,
)
from dppnotifier.app.scrapper import TrafficEvent, fetch_events

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


def notify(notifiers: List[NotifierSubscribers], events: List[TrafficEvent]):
    for notifier_subscribers in notifiers:
        with notifier_subscribers.notifier as notifier:
            for event in events:
                subs = filter_subscriber(
                    event=event, subscribers=notifier_subscribers.subscribers
                )
                try:
                    notifier.notify(event, subs)
                except BaseException as exc:  # pylint: disable=broad-except
                    # Catch everything so that other events and notifiers can
                    # continue
                    _LOGGER.error(exc.args[0])


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


def inactivate_dead_events(
    null_end_date_events: Dict[str, TrafficEvent],
    events_db: DynamoTrafficEventsDb,
) -> None:
    now = datetime.now()
    now_2d = now - timedelta(days=2)
    for event in null_end_date_events.values():
        if event.start_date < now_2d:
            event.active = False
            event.end_date = now
            try:
                update_db(event, events_db)
            except FailedUpsertEvent:
                continue
            _LOGGER.info('Inactivated dead event %s', event.event_id)


def inactivate_expired_events(
    active_expired: Dict[str, TrafficEvent], events_db: DynamoTrafficEventsDb
) -> None:
    for event in active_expired.values():
        event.active = False
        try:
            update_db(event, events_db)
        except FailedUpsertEvent:
            continue
        _LOGGER.info('Inactivated expired event %s', event.event_id)


# pylint: disable=unused-argument
def run_job(
    trigger_event: Optional[Any] = None, context: Optional[Any] = None
):
    to_notify = []
    init_logger()

    events_db = DynamoTrafficEventsDb(
        table_name=os.getenv('EVENTS_TABLE', 'dpp-notifier-events')
    )
    null_end_date_events = events_db.get_end_date_null_events()
    active_expired = events_db.get_active_but_expired_events()

    _LOGGER.info('Fetching current events')
    for event in fetch_events():
        db_event = events_db.find_by_id(event.event_id)
        if event.active and db_event is None:
            to_notify.append(event)
            _LOGGER.info(event.to_log_message())

        try:
            del null_end_date_events[event.event_id]
        except KeyError:
            pass
        try:
            del active_expired[event.event_id]
        except KeyError:
            pass

        if event != db_event:
            try:
                update_db(event, events_db)
            except FailedUpsertEvent:
                continue

    inactivate_dead_events(
        null_end_date_events=null_end_date_events, events_db=events_db
    )

    inactivate_expired_events(
        active_expired=active_expired, events_db=events_db
    )

    if len(to_notify) == 0:
        _LOGGER.info('No new events - terminating')
        return

    subs_db = DynamoSubscribersDb(
        table_name=os.getenv('SUBSCRIBERS_TABLE', 'dpp-notifier-recepients')
    )
    notifiers = build_notifiers(subs_db)
    notify(notifiers, to_notify)

    _LOGGER.info('Job finished')


class FailedUpsertEvent(Exception):
    """Upsert to DynamoDB failed"""
