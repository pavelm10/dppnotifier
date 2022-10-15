import os
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from dppnotifier.app.constants import AWS_REGION
from dppnotifier.app.dpptypes import Notifiers, Subscriber, TrafficEvent


class DynamoDb:
    """Base class that initializes Dynamo DB table client"""

    def __init__(self, table_name: str):
        profile = os.environ.get('AWS_PROFILE')
        session = boto3.Session(profile_name=profile)
        self._client = session.resource('dynamodb', region_name=AWS_REGION)
        self._table = self._client.Table(table_name)


class DynamoTrafficEventsDb(DynamoDb):
    """Traffic events DB client"""

    PARTITION_KEY_NAME = 'event_type'
    PARTITION_KEY_VALUE = 'dpp'
    SORT_KEY_NAME = 'event_id'

    def find_by_id(self, event_id: str) -> Optional[TrafficEvent]:
        """Finds the event by its ID.

        Parameters
        ----------
        event_id : str
            The event ID to be found

        Returns
        -------
        Optional[TrafficEvent]
            If the event is found by its ID returns the event else None

        Raises
        ------
        ValueError
            When there are more events with the same ID - should never happen.
        """
        response = self._table.query(
            KeyConditionExpression=Key(self.PARTITION_KEY_NAME).eq(
                self.PARTITION_KEY_VALUE
            )
            & Key(self.SORT_KEY_NAME).eq(event_id),
        )
        items = response['Items']
        if len(items) > 1:
            raise ValueError(f'Too many events with ID {event_id}')

        if len(items) == 0:
            return None

        entity = items[0]
        return TrafficEvent.from_entity(entity)

    def upsert_event(self, event: TrafficEvent):
        """Upserts the event in the DB.

        Parameters
        ----------
        event : TrafficEvent
            The event to be upserted.
        """
        attr_updates = {}
        entity = event.to_entity()
        del entity[self.SORT_KEY_NAME]

        for attr, value in entity.items():
            attr_updates[attr] = {'Value': value, 'Action': 'PUT'}

        self._table.update_item(
            Key={
                self.PARTITION_KEY_NAME: self.PARTITION_KEY_VALUE,
                self.SORT_KEY_NAME: event.event_id,
            },
            AttributeUpdates=attr_updates,
        )

    def get_active_events(self) -> Dict[str, TrafficEvent]:
        """Gets all events that are active in the DB.

        Returns
        -------
        Dict[str, TrafficEvent]
            Mapping of event ID and the event instance.
        """
        response = self._table.query(
            KeyConditionExpression=Key(self.PARTITION_KEY_NAME).eq(
                self.PARTITION_KEY_VALUE
            ),
            FilterExpression=Attr('active').eq(1),
        )
        items = response['Items']
        return {
            item['event_id']: TrafficEvent.from_entity(item) for item in items
        }


class DynamoSubscribersDb(DynamoDb):
    """Subscribers DB client"""

    def add_subscriber(self, subscriber: Subscriber):
        """Adds the subscriber to the DB.

        Parameters
        ----------
        subscriber : Subscriber
            The subscriber to be added.
        """
        item = subscriber.to_entity()
        self._table.put_item(Item=item)

    def get_subscriber(self, notifier_type: Notifiers) -> List[Subscriber]:
        """Gets list of all subscribers based on the notifier's type.

        Parameters
        ----------
        notifier_type : Notifiers
            The notifier type to filter the notifiers

        Returns
        -------
        List[Subscriber]
            List of all subscribers with the given notifier type.
        """
        response = self._table.query(
            KeyConditionExpression=Key('notifier').eq(notifier_type.value)
        )
        items = response['Items']
        subscribers = []
        for item in items:
            subscriber = Subscriber.from_entity(item)
            subscribers.append(subscriber)
        return subscribers
