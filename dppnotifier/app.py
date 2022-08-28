from typing import Any, Dict, List, Tuple

from dppnotifier.db import DynamoSubscribersDb, DynamoTrafficEventsDb
from dppnotifier.log import init_logger
from dppnotifier.notifier import AwsSesNotifier, LogNotifier, WhatsAppNotifier
from dppnotifier.scrapper import TrafficEvent, fetch_events
from dppnotifier.types import NotifierSubscribers, Recepient

_LOGGER = init_logger(__name__)


class DppNotificationApp:
    def __init__(self):
        self._aws_notifier = AwsSesNotifier()
        self._whatsapp_notifier = WhatsAppNotifier()
        self._log_notifier = LogNotifier()

        self.events_db = DynamoTrafficEventsDb(
            table_name='dpp-notifier-events'
        )
        self.subs_db = DynamoSubscribersDb(
            table_name='dpp-notifier-recepients'
        )
        self._notifiers = self._build_notifiers()

    def _build_notifiers(self) -> List[NotifierSubscribers]:
        possible_notifiers = (self._aws_notifier, self._whatsapp_notifier)
        notifiers = []
        for notifier in possible_notifiers:
            if notifier.enabled:
                notifiers.append(
                    NotifierSubscribers(
                        notifier=notifier,
                        subscribers=self.subs_db.get_recepients(
                            notifier_type=notifier.notifier_type
                        ),
                    )
                )
                _LOGGER.info(
                    '%s notifier registered', notifier.notifier_type.value
                )

        _LOGGER.info('Notifiers and subscribers set up')
        return notifiers

    def _notify(self, event: TrafficEvent):
        for notifier_subscribers in self._notifiers:
            subs = self._filter_subscriber(
                event, notifier_subscribers.subscribers
            )
            if len(subs) > 0:
                notifier_subscribers.notifier.notify(event, subs)

    def __call__(self, *args, **kwds):
        _LOGGER.info('Fetching current events')
        for event in fetch_events():
            self._log_notifier.notify(event)
            db_event = self.events_db.find_by_id(event.event_id)

            try:
                self.events_db.upsert_event(event)
            except (ValueError, IndexError, KeyError) as exc:
                _LOGGER.error(
                    'Failed to upsert the event - notification skipped'
                )
                _LOGGER.error(exc)
                continue

            if event.active and db_event is None:
                self._notify(event)

    @staticmethod
    def _filter_subscriber(event, subscribers) -> Tuple[Recepient]:
        subs = []
        for sub in subscribers:
            if set(sub.lines).issubset(set(event.lines)):
                subs.append(sub)
        return tuple(subs)


def main():
    DppNotificationApp()()


if __name__ == '__main__':
    main()
