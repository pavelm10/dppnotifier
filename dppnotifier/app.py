from pathlib import Path
from typing import Dict, List

from dppnotifier.db import BaseDb, JsonDb
from dppnotifier.log import init_logger
from dppnotifier.notifier import AwsSesNotifier, LogNotifier, WhatsAppNotifier
from dppnotifier.scrapper import TrafficEvent, fetch_events
from dppnotifier.types import Recepient

_LOGGER = init_logger(__name__)


def notify(issues: List[TrafficEvent]):
    notifiers = [
        AwsSesNotifier(),
        WhatsAppNotifier(),
        LogNotifier(),
    ]
    aws_recepients = (Recepient('marek.pavelka12@gmail.com'),)
    whatsapp_recepients = ()
    log_recepients = ()
    recepients = [aws_recepients, whatsapp_recepients, log_recepients]
    for notifier, recepient_list in zip(notifiers, recepients):
        notifier.notify(issues, recepient_list)


def update_db(db: BaseDb, events: List[TrafficEvent]):
    for event in events:
        db.upsert_event(event)
    _LOGGER.info('DB updated')


def filter_new_events(
    db_events: Dict[str, TrafficEvent], active_events: List[TrafficEvent]
) -> List[TrafficEvent]:
    return [ev for ev in active_events if ev.event_id not in db_events.keys()]


def filter_active_events(events: List[TrafficEvent]) -> List[TrafficEvent]:
    return [ev for ev in events if ev.active]


def main():
    db = JsonDb(file_path=Path('data/events.json'))
    _LOGGER.info('Fetching current events')
    events = fetch_events()
    active_events = filter_active_events(events)
    new_events = filter_new_events(
        db_events=db.db, active_events=active_events
    )
    notify(new_events)
    update_db(db=db, events=events)


if __name__ == '__main__':
    main()
