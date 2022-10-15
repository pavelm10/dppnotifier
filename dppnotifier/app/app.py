import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

from dppnotifier.app.db import DynamoSubscribersDb, DynamoTrafficEventsDb
from dppnotifier.app.dpptypes import NotifierSubscribers, Subscriber
from dppnotifier.app.historizer import store_html
from dppnotifier.app.log import init_logger
from dppnotifier.app.notifier import (
    AwsSesNotifier,
    TelegramNotifier,
    WhatsAppNotifier,
)
from dppnotifier.app.parser import TrafficEvent, fetch_events, is_event_active
from dppnotifier.app.utils import utcnow_localized

_LOGGER = logging.getLogger(__name__)

CURRENT_URL = 'https://pid.cz/mimoradnosti/'


def scrape() -> bytes:
    """Scraps the webpage with the traffic events for the HTML content.

    Returns
    -------
    bytes
        HTML content
    """
    page = requests.get(CURRENT_URL, timeout=30)
    return page.content


def build_notifiers(
    subscribers_db: DynamoSubscribersDb,
) -> List[NotifierSubscribers]:
    """Based on the subscribers DB initializes particular notifiers and
    builds mapping between notifier and its subscribers.

    Parameters
    ----------
    subscribers_db : DynamoSubscribersDb
        Subscribers DB client

    Returns
    -------
    List[NotifierSubscribers]
        List of NotifierSubscribers instances
    """
    possible_notifiers = (AwsSesNotifier, TelegramNotifier, WhatsAppNotifier)
    notifiers = []
    for notifier_class in possible_notifiers:
        subscribers = subscribers_db.get_subscribers(
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
    """For each initialized notifier filters subscribers for the event
    and notifies the subscribers.

    Parameters
    ----------
    notifiers : List[NotifierSubscribers]
         List of NotifierSubscribers instances
    events : List[TrafficEvent]
        List of the traffic events
    """
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
    """Filters the subscribers for the event so that only subscribers that are
    interested in the event based on the lines set are notified.

    Parameters
    ----------
    event : TrafficEvent
        The traffic event
    subscribers : List[Subscriber]
        List of subscribers

    Returns
    -------
    Tuple[Subscriber]
        Filtered subscribers
    """
    subs = []
    for sub in subscribers:
        if len(sub.lines) == 0:
            subs.append(sub)
            continue
        if set(sub.lines).intersection(set(event.lines)):
            subs.append(sub)
    return tuple(subs)


def update_db(event: TrafficEvent, events_db: DynamoTrafficEventsDb):
    """Updates the event in the events DB.

    Parameters
    ----------
    event : TrafficEvent
        The traffic event to update
    events_db : DynamoTrafficEventsDb
        Events DB client

    Raises
    ------
    FailedUpsertEvent
        When the event failed to be updated.
    """
    try:
        events_db.upsert_event(event)
    except (ValueError, IndexError, KeyError) as exc:
        _LOGGER.error(exc)
        raise FailedUpsertEvent(event.event_id) from exc


# pylint: disable=unused-argument
def run_job(
    trigger_event: Optional[Any] = None, context: Optional[Any] = None
):
    """The main entrypoint method of the AWS lambda job.

    Parameters
    ----------
    trigger_event : Optional[Any], optional
        AWS lambda trigger event object, unused.
    context : Optional[Any], optional
        AWS lambda context, unused.
    """
    to_notify = []
    save_html_content = False
    init_logger()

    events_db = DynamoTrafficEventsDb(
        table_name=os.getenv('EVENTS_TABLE', 'dpp-notifier-events')
    )

    db_active_events = events_db.get_active_events()
    current_events = set()

    html_content = scrape()

    _LOGGER.info('Fetching current events')
    for event in fetch_events(html_content):
        db_event = db_active_events.get(event.event_id)
        current_events.add(event.event_id)

        if db_event is not None and db_event.start_date is not None:
            # keep the original start date
            event.start_date = db_event.start_date

        if event != db_event:
            save_html_content = True
            try:
                update_db(event, events_db)
            except FailedUpsertEvent:
                _LOGGER.error('Failed to upsert the event %s', event.event_id)
                continue
            else:
                _LOGGER.info('Upserted event %s', event.event_id)
                if event.active and db_event is None:
                    to_notify.append(event)
                    _LOGGER.info(event.to_log_message())

    if save_html_content:
        # Temporarily store HTML to S3 bucket to collect some test data
        store_html(html_content)

    db_active = set(db_active_events.keys()) - current_events
    db_active_events = {eid: db_active_events[eid] for eid in db_active}
    handle_active_db_events(db_active_events, events_db)

    if len(to_notify) == 0:
        _LOGGER.info('No new events - terminating')
        return

    subs_db = DynamoSubscribersDb(
        table_name=os.getenv('SUBSCRIBERS_TABLE', 'dpp-notifier-recepients')
    )
    notifiers = build_notifiers(subs_db)
    notify(notifiers, to_notify)

    _LOGGER.info('Job finished')


def handle_active_db_events(
    events: Dict[str, TrafficEvent], events_db: DynamoTrafficEventsDb
) -> None:
    """For each active event in the DB downloads the event HTML content
    and checks if the event is still active. If it is not active, sets it to
    inactive state in the DB.

    Parameters
    ----------
    events : Dict[str, TrafficEvent]
        Mapping of event ID and the event instance
    events_db : DynamoTrafficEventsDb
        Events DB client
    """
    for event in events.values():
        handle_active_event(event, events_db)


def handle_active_event(
    event: TrafficEvent, events_db: DynamoTrafficEventsDb
) -> None:
    """For the active event downloads the event HTML content and checks if the
    event is still active. If it is not active, sets it to inactive state in
    the DB.

    Parameters
    ----------
    event : TrafficEvent
        Mapping of event ID and the event instance
    events_db : DynamoTrafficEventsDb
        Events DB client
    """
    res = requests.get(event.url, timeout=30)
    active = is_event_active(res.content)
    if not active:
        event.active = False
        event.end_date = utcnow_localized()
        try:
            update_db(event=event, events_db=events_db)
            _LOGGER.info('Deactivated finished event %s', event.event_id)
        except FailedUpsertEvent:
            _LOGGER.error(
                'Failed to deactivate finished event %s', event.event_id
            )


class FailedUpsertEvent(Exception):
    """Upsert to DynamoDB failed"""
