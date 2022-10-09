import logging
import os
from abc import ABC, abstractmethod
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from dppnotifier.app.constants import AWS_REGION
from dppnotifier.app.dpptypes import Notifiers, Subscriber, TrafficEvent

_LOGGER = logging.getLogger(__name__)


class SubscribersDb(ABC):
    @abstractmethod
    def find_by_uri(self, uri: str) -> Optional[Subscriber]:
        raise NotImplementedError

    @abstractmethod
    def find_by_notifier(
        self, notifier: Notifiers
    ) -> Optional[List[Subscriber]]:
        raise NotImplementedError

    @abstractmethod
    def upsert_subscriber(self, subscriber: Subscriber):
        raise NotImplementedError

    @abstractmethod
    def delete_subscriber(self, subscriber: Subscriber):
        raise NotImplementedError


class DynamoDb:
    def __init__(self, table_name: str):
        profile = os.environ.get('AWS_PROFILE')
        session = boto3.Session(profile_name=profile)
        self._client = session.resource('dynamodb', region_name=AWS_REGION)
        self._table = self._client.Table(table_name)


class DynamoTrafficEventsDb(DynamoDb):
    PARTITION_KEY_NAME = 'event_type'
    PARTITION_KEY_VALUE = 'dpp'
    SORT_KEY_NAME = 'event_id'

    def find_by_id(self, event_id: str) -> Optional[TrafficEvent]:
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
        _LOGGER.info('Upserted event %s', event.event_id)

    def get_active_events(self):
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


class DynamoSubscribersDb(SubscribersDb, DynamoDb):
    def add_subscriber(self, subscriber: Subscriber):
        item = subscriber.to_entity()
        _LOGGER.info(item)
        self._table.put_item(Item=item)
        _LOGGER.info('Added subscriber')

    def get_subscriber(self, notifier_type: Notifiers) -> List[Subscriber]:
        response = self._table.query(
            KeyConditionExpression=Key('notifier').eq(notifier_type.value)
        )
        items = response['Items']
        subscribers = []
        for item in items:
            subscriber = Subscriber.from_entity(item)
            subscribers.append(subscriber)
        return subscribers

    def find_by_uri(self, uri: str) -> Optional[Subscriber]:
        raise NotImplementedError

    def find_by_notifier(
        self, notifier: Notifiers
    ) -> Optional[List[Subscriber]]:
        raise NotImplementedError

    def upsert_subscriber(self, subscriber: Subscriber):
        raise NotImplementedError

    def delete_subscriber(self, subscriber: Subscriber):
        raise NotImplementedError
