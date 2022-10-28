from dppnotifier.app.db import DynamoSubscribersDb, DynamoTrafficEventsDb
from dppnotifier.app.dpptypes import Notifiers, Subscriber

SUB_DB = {
    Notifiers.AWS_SES: [
        Subscriber(
            notifier=Notifiers.AWS_SES,
            uri='uri1',
            user='user1',
            lines=('1', 'A'),
        ),
        Subscriber(
            notifier=Notifiers.AWS_SES,
            uri='uri2',
            user='user2',
        ),
    ],
    Notifiers.WHATSAPP: [],
    Notifiers.TELEGRAM: [
        Subscriber(
            notifier=Notifiers.TELEGRAM,
            uri='uri3',
            user='user3',
            lines=('16', '9'),
        ),
        Subscriber(
            notifier=Notifiers.TELEGRAM,
            uri='uri4',
            user='user4',
            lines=('7', '16', 'A'),
            time_filter_expression=(
                1,
                1,
                1,
                1,
                1,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                1,
                1,
                1,
                1,
                0,
                0,
                0,
                0,
                1,
                1,
                1,
                1,
                1,
                1,
                0,
                0,
                0,
            ),
        ),
    ],
}


class DynamoSubscribersDbMock(DynamoSubscribersDb):
    def get_subscribers(self, notifier_type):
        return SUB_DB[notifier_type]


class DynamoTrafficEventsDbMock(DynamoTrafficEventsDb):
    def __init__(self, events, table_name: str):
        super().__init__(table_name)
        self.events = events

    def get_active_events(self):
        return {ev.event_id: ev for ev in self.events}
