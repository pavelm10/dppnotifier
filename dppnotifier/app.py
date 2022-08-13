from pathlib import Path
from typing import Dict, List

from dppnotifier.db import BaseDb, JsonDb
from dppnotifier.notifier import GmailNotifier, WhatsAppNotifier
from dppnotifier.scrapper import TrafficEvent, fetch_events


def notify(issues: List[TrafficEvent]):
    gmail = GmailNotifier()
    whatsapp = WhatsAppNotifier()
    gmail.notify(issues)
    whatsapp.notify(issues)
    for issue in issues:
        print(issue)


def update_db(db: BaseDb, events: List[TrafficEvent]):
    for event in events:
        db.upsert_event(event)


def filter_new_events(
    db_events: Dict[str, TrafficEvent], active_events: List[TrafficEvent]
) -> List[TrafficEvent]:
    return [ev for ev in active_events if ev.event_id not in db_events.keys()]


def filter_active_events(events: List[TrafficEvent]) -> List[TrafficEvent]:
    return [ev for ev in events if ev.active]


def main():
    db = JsonDb(file_path=Path('data/events.json'))
    events = fetch_events()
    active_events = filter_active_events(events)
    new_events = filter_new_events(
        db_events=db.db, active_events=active_events
    )
    notify(new_events)
    update_db(db=db, events=events)


if __name__ == '__main__':
    main()
