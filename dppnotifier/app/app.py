import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests
import tenacity
from requests.exceptions import ReadTimeout

from dppnotifier.app.db import DynamoSubscribersDb, DynamoTrafficEventsDb
from dppnotifier.app.dpptypes import NotifierSubscribers, Subscriber
from dppnotifier.app.historizer import store_html
from dppnotifier.app.log import init_logger
from dppnotifier.app.notifier import (
    AlertTelegramNotifier,
    AwsSesNotifier,
    EventTelegramNotifier,
    WhatsAppNotifier,
)
from dppnotifier.app.parser import TrafficEvent, fetch_events, is_event_active
from dppnotifier.app.utils import utcnow_localized

_LOGGER = logging.getLogger(__name__)

CURRENT_URL = 'https://pid.cz/mimoradnosti/'


@tenacity.retry(
    retry=tenacity.retry_if_exception_type(ReadTimeout),
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait.wait_exponential(multiplier=5),
)
def _get_request(url: str) -> requests.Response:
    """Wraps requests.get in order to implement retrying on timeout

    Parameters
    ----------
    url : str
        URL to call the request to

    Returns
    -------
    requests.Response
        Server response
    """
    return requests.get(url, timeout=5)


def scrape(url: str, alert_notifier: AlertTelegramNotifier) -> Optional[bytes]:
    """Scraps the webpage url for the HTML content.

    Parameters
    ----------
    url : str
        URL to scrape
    alert_notifier : AlertTelegramNotifier
        Alerting notifier

    Returns
    -------
    Optional[bytes]
        HTML content, if times out returns None
    """
    last_exception = None
    try:
        page = _get_request(url)
    except ReadTimeout as exc:
        last_exception = exc
        return None
    except Exception as exc:
        last_exception = exc
        raise
    finally:
        if last_exception is not None:
            _LOGGER.error(last_exception.args[0])
            alert_notifier.send_alert(alert=last_exception.args[0])
    return page.content


def build_notifiers(
    subscribers_db: DynamoSubscribersDb, alert_notifier: AlertTelegramNotifier
) -> List[NotifierSubscribers]:
    """Based on the subscribers DB initializes particular notifiers and
    builds mapping between notifier and its subscribers.

    Parameters
    ----------
    subscribers_db : DynamoSubscribersDb
        Subscribers DB client
    alert_notifier : AlertTelegramNotifier
        Alerting notifier

    Returns
    -------
    List[NotifierSubscribers]
        List of NotifierSubscribers instances
    """
    possible_notifiers = (
        AwsSesNotifier,
        EventTelegramNotifier,
        WhatsAppNotifier,
    )
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
    if len(notifiers) == 0:
        msg = 'No notifier built - no notification will be send'
        _LOGGER.warning(msg)
        alert_notifier.send_alert(alert=msg)
    else:
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
    subs = [sub for sub in subscribers if sub.is_interested(event=event)]
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
    raw_data_bucket_name = os.environ['AWS_S3_RAW_DATA_BUCKET']
    alert_subscriber_uri = os.environ.get('ALERT_SUBSCRIBER_URI')
    if alert_subscriber_uri is not None:
        alert_subscriber_uri = int(alert_subscriber_uri)

    enable_debug_input_storing = 'HISTORIZE' in os.environ
    save_html_content = False
    init_logger()

    alerter_notifier = AlertTelegramNotifier(
        alert_subscriber_uri=alert_subscriber_uri
    )
    with alerter_notifier as alerter:

        events_db = DynamoTrafficEventsDb(
            table_name=os.getenv('EVENTS_TABLE', 'dpp-notifier-events')
        )

        db_active_events = events_db.get_active_events()
        current_events = set()

        html_content = scrape(url=CURRENT_URL, alert_notifier=alerter)
        if html_content is None:
            _LOGGER.error('Failed to scrape the traffic events - terminating')
            return

        _LOGGER.info('Fetching current events')
        try:
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
                        _LOGGER.error(
                            'Failed to upsert the event %s', event.event_id
                        )
                        continue
                    else:
                        _LOGGER.info('Upserted event %s', event.event_id)
                        if event.active and db_event is None:
                            to_notify.append(event)
                            _LOGGER.info(event.to_log_message())
        except Exception as exc:
            _LOGGER.error(exc.args[0])
            store_html(html_content, raw_data_bucket_name)
            alerter.send_alert(exc.args[0])
            return

        if save_html_content and enable_debug_input_storing:
            # Temporarily store HTML to S3 bucket to collect some test data
            store_html(html_content, raw_data_bucket_name)

        db_active = set(db_active_events.keys()) - current_events
        db_active_events = {eid: db_active_events[eid] for eid in db_active}
        handle_active_db_events(
            events=db_active_events,
            events_db=events_db,
            alert_notifier=alerter,
        )

        if len(to_notify) == 0:
            _LOGGER.info('No new events - terminating')
            return

        subs_db = DynamoSubscribersDb(
            table_name=os.getenv(
                'SUBSCRIBERS_TABLE', 'dpp-notifier-recepients'
            )
        )

        notifiers = build_notifiers(
            subscribers_db=subs_db, alert_notifier=alerter
        )

        notify(notifiers, to_notify)
        _LOGGER.info('Job finished')


def handle_active_db_events(
    events: Dict[str, TrafficEvent],
    events_db: DynamoTrafficEventsDb,
    alert_notifier: AlertTelegramNotifier,
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
    alert_notifier : AlertTelegramNotifier
        Alerting notifier
    """
    for event in events.values():
        handle_active_event(
            event=event, events_db=events_db, alert_notifier=alert_notifier
        )


def handle_active_event(
    event: TrafficEvent,
    events_db: DynamoTrafficEventsDb,
    alert_notifier: AlertTelegramNotifier,
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
    alert_notifier : AlertTelegramNotifier
        Alerting notifier
    """
    html_content = scrape(url=event.url, alert_notifier=alert_notifier)
    if html_content is None:
        _LOGGER.error('Failed to scrape event web page - skipping')
        return

    active = is_event_active(html_content)
    if not active:
        event.active = False
        event.end_date = utcnow_localized()
        try:
            update_db(event=event, events_db=events_db)
            _LOGGER.info('Deactivated finished event %s', event.event_id)
        except FailedUpsertEvent:
            msg = f'Failed to deactivate finished event {event.event_id}'
            _LOGGER.error(msg)
            alert_notifier.send_alert(alert=msg)


class FailedUpsertEvent(Exception):
    """Upsert to DynamoDB failed"""
