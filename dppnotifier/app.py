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
    arpg = argparse.ArgumentParser(description='')
    arpg.add_argument(
        '-a',
        '--active-only',
        action='store_true',
        help='If set only active events will be used to notification',
    )

    pargs = arpg.parse_args()
    active_only = pargs.active_only

    db = JsonDb(file_path=Path('data/events.json'))
    issues = fetch_events(active_only=active_only)
    notify(issues)
    update_db(db=db, events=issues)


if __name__ == '__main__':
    main()
