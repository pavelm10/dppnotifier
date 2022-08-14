from pathlib import Path

from dppnotifier.db import JsonDb
from dppnotifier.log import init_logger
from dppnotifier.notifier import AwsSesNotifier, LogNotifier, WhatsAppNotifier
from dppnotifier.scrapper import TrafficEvent, fetch_events
from dppnotifier.types import Notifiers, Recepient

_LOGGER = init_logger(__name__)


def notify(issue: TrafficEvent):
    notifiers = [
        AwsSesNotifier(),
        WhatsAppNotifier(),
        LogNotifier(),
    ]
    aws_recepients = (
        Recepient(
            notifier=Notifiers.AWS_SES,
            uri='marek.pavelka12@gmail.com',
            user='Marek Pavelka',
        ),
    )
    whatsapp_recepients = ()
    log_recepients = ()
    recepients = [aws_recepients, whatsapp_recepients, log_recepients]
    for notifier, recepient_list in zip(notifiers, recepients):
        notifier.notify([issue], recepient_list)


def main():
    db = JsonDb(file_path=Path('data/events.json'))
    _LOGGER.info('Fetching current events')
    for event in fetch_events():
        db.upsert_event(event)
        if event.active and event.event_id not in db.db.keys():
            notify(event)


if __name__ == '__main__':
    main()
