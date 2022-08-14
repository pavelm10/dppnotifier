from pathlib import Path
from typing import Set

from dppnotifier.db import JsonTrafficEventsDb
from dppnotifier.log import init_logger
from dppnotifier.notifier import AwsSesNotifier, LogNotifier, WhatsAppNotifier
from dppnotifier.scrapper import TrafficEvent, fetch_events
from dppnotifier.types import Notifiers, Recepient

_LOGGER = init_logger(__name__)


class DppNotificationApp:
    def __init__(self) -> None:
        self._aws_notifier = AwsSesNotifier()
        self._whatsapp_notifer = WhatsAppNotifier()
        self._log_notifier = LogNotifier()
        self._get_subscribers()
        self.db = JsonTrafficEventsDb(file_path=Path('data/events.json'))

    def _get_subscribers(self):
        self._aws_recepients = (
            Recepient(
                notifier=Notifiers.AWS_SES,
                uri='marek.pavelka12@gmail.com',
                user='Marek Pavelka',
            ),
        )
        self._whatsapp_recepients = ()
        self._log_recepients = ()

    def _notify(self, event: TrafficEvent):
        aws_subs = self._filter_subscriber(event, self._aws_recepients)
        whatsapp_subs = self._filter_subscriber(
            event, self._whatsapp_recepients
        )

        self._aws_notifier.notify([event], tuple(aws_subs))
        self._whatsapp_notifer.notify([event], tuple(whatsapp_subs))
        self._log_notifier.notify([event])

    def __call__(self, *args, **kwds):
        _LOGGER.info('Fetching current events')
        for event in fetch_events():
            try:
                self.db.upsert_event(event)
            except (ValueError, IndexError, KeyError) as exc:
                _LOGGER.error(
                    'Failed to upsert the event - notification skipped'
                )
                _LOGGER.error(exc)
                continue

            if event.active and event.event_id not in self.db.db.keys():
                self._notify(event)

    @staticmethod
    def _filter_subscriber(event, subscribers) -> Set[Recepient]:
        subs = []
        for sub in subscribers:
            if set(sub.lines).issubset(set(event.lines)):
                subs.append(sub)
        return set(subs)


def main():
    app = DppNotificationApp()
    app()


if __name__ == '__main__':
    main()
