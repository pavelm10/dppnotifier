import argparse
from pathlib import Path
from typing import List

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


def main():
    db = JsonDb(file_path=Path('data/events.json'))
    issues = fetch_events()
    active_issues = [iss for iss in issues if iss.active]
    notify(active_issues)
    update_db(db=db, events=issues)


if __name__ == '__main__':
    main()
