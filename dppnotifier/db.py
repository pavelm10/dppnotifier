# TODO: class to store traffic events to NoSQL database and is also able to
# update its active state. It is needed for notifier so that it is known,
# which event was already notified or not.

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from dppnotifier.log import init_logger
from dppnotifier.types import Notifiers, Recepient, TrafficEvent

_LOGGER = init_logger(__name__)


class TrafficEventsDb(ABC):
    @abstractmethod
    def find_by_id(self, event_id: str) -> Optional[TrafficEvent]:
        raise NotImplementedError

    @abstractmethod
    def upsert_event(self, event: TrafficEvent):
        raise NotImplementedError


class SubscribersDb(ABC):
    @abstractmethod
    def find_by_uri(self, uri: str) -> Optional[Recepient]:
        raise NotImplementedError

    @abstractmethod
    def find_by_notifier(
        self, notifier: Notifiers
    ) -> Optional[List[Recepient]]:
        raise NotImplementedError

    @abstractmethod
    def upsert_subscriber(self, subscriber: Recepient):
        raise NotImplementedError

    @abstractmethod
    def delete_subscriber(self, subscriber: Recepient):
        raise NotImplementedError


class DynamoDb:
    AWS_REGION = "eu-central-1"

    def __init__(
        self, table_name: str, profile: Optional[str] = 'dppnotifier'
    ):
        session = boto3.Session(profile_name=profile)
        self._client = session.resource(
            'dynamodb', region_name=self.AWS_REGION
        )
        self._table = self._client.Table(table_name)


class JsonTrafficEventsDb(TrafficEventsDb):
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._load()
        _LOGGER.info('DB loaded')

    def _load(self):
        if not self._file_path.exists():
            self.db = {}
            return

        with open(self._file_path, 'r', encoding='utf-8') as file:
            self.db = json.load(file)

    def _dump(self):
        if len(self.db) == 0:
            return

        with open(self._file_path, 'w', encoding='utf-8') as file:
            json.dump(self.db, file, ensure_ascii=False)

    def find_by_id(self, event_id: str) -> Optional[TrafficEvent]:
        event = self.db.get(event_id)
        if event is not None:
            event = TrafficEvent(**event)
        return event

    def upsert_event(self, event: TrafficEvent):
        self.db[event.event_id] = event.to_entity()
        self._dump()


class DynamoTrafficEventsDb(TrafficEventsDb, DynamoDb):
    def find_by_id(self, event_id: str) -> Optional[TrafficEvent]:
        response = self._table.query(
            KeyConditionExpression=Key('event_type').eq('dpp')
            & Key('event_id').eq(event_id),
        )
        items = response['Items']
        if len(items) > 1:
            raise ValueError(f'Too many events with ID {event_id}')
        elif len(items) == 0:
            return None
        else:
            entity = items[0]
            return TrafficEvent.from_entity(entity)

    def upsert_event(self, event: TrafficEvent):
        attr_updates = {}
        entity = event.to_entity()
        del entity['event_id']

        for attr, value in entity.items():
            attr_updates[attr] = {'Value': value, 'Action': 'PUT'}

        self._table.update_item(
            Key={'event_type': 'dpp', 'event_id': event.event_id},
            AttributeUpdates=attr_updates,
        )
        _LOGGER.info('Upserted event %s', event.event_id)


class DynamoSubscribersDb(SubscribersDb, DynamoDb):
    def add_recepient(self, recepient: Recepient):
        item = recepient.to_entity()
        _LOGGER.info(item)
        self._table.put_item(Item=item)
        _LOGGER.info('Added recepient')

    def get_recepients(self, notifier_type: Notifiers) -> List[Recepient]:
        response = self._table.query(
            KeyConditionExpression=Key('notifier').eq(notifier_type.value)
        )
        items = response['Items']
        recepients = []
        for item in items:
            recepient = Recepient.from_entity(item)
            recepients.append(recepient)
        return recepients

    def find_by_uri(self, uri: str) -> Optional[Recepient]:
        raise NotImplementedError

    def find_by_notifier(
        self, notifier: Notifiers
    ) -> Optional[List[Recepient]]:
        raise NotImplementedError

    def upsert_subscriber(self, subscriber: Recepient):
        raise NotImplementedError

    def delete_subscriber(self, subscriber: Recepient):
        raise NotImplementedError
