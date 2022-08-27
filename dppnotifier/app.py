from typing import Tuple

from dppnotifier.db import DynamoSubscribersDb, DynamoTrafficEventsDb
from dppnotifier.log import init_logger
from dppnotifier.notifier import AwsSesNotifier, LogNotifier, WhatsAppNotifier
from dppnotifier.scrapper import TrafficEvent, fetch_events
from dppnotifier.types import Notifiers, Recepient

_LOGGER = init_logger(__name__)


class DppNotificationApp:
    def __init__(self):
        self._aws_notifier = AwsSesNotifier()
        self._whatsapp_notifer = WhatsAppNotifier()
        self._log_notifier = LogNotifier()

        self.events_db = DynamoTrafficEventsDb(
            table_name='dpp-notifier-events'
        )
        self.subs_db = DynamoSubscribersDb(
            table_name='dpp-notifier-recepients'
        )
        self._aws_subscribers = ()
        self._whatsapp_subscribers = ()

    def _get_subscribers(self):
        self._aws_subscribers = self.subs_db.get_recepients(
            notifier_type=Notifiers.AWS_SES
        )
        self._whatsapp_subscribers = self.subs_db.get_recepients(
            notifier_type=Notifiers.WHATSAPP
        )

    def _notify(self, event: TrafficEvent):
        aws_subs = self._filter_subscriber(event, self._aws_subscribers)
        whatsapp_subs = self._filter_subscriber(
            event, self._whatsapp_subscribers
        )

        self._aws_notifier.notify(event, aws_subs)
        self._whatsapp_notifer.notify(event, whatsapp_subs)

    def __call__(self, *args, **kwds):
        _LOGGER.info('Getting subscribers')
        self._get_subscribers()

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
