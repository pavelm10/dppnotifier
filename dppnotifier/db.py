# TODO: class to store traffic events to NoSQL database and is also able to
# update its active state. It is needed for notifier so that it is known,
# which event was already notified or not.

import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from dppnotifier.log import init_logger
from dppnotifier.types import Notifiers, Recepient, TrafficEvent

_LOGGER = init_logger(__name__)


class BaseDb(ABC):
    @abstractmethod
    def find_by_id(self, event_id: str) -> Optional[TrafficEvent]:
        raise NotImplementedError

    @abstractmethod
    def upsert_event(self, event: TrafficEvent):
        raise NotImplementedError


class JsonDb(BaseDb):
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


class DynamoDb(BaseDb):
    AWS_REGION = "eu-central-1"

    def __init__(
        self, table_name: str, profile: Optional[str] = 'dppnotifier'
    ):
        session = boto3.Session(profile_name=profile)
        self._client = session.resource(
            'dynamodb', region_name=self.AWS_REGION
        )
        self._table = self._client.Table(table_name)

    def find_by_id(self, event_id: str) -> Optional[TrafficEvent]:
        raise NotImplementedError

    def upsert_event(self, event: TrafficEvent):
        raise NotImplementedError

    def add_recepient(self, recepient: Recepient):
        if recepient.notifier != Notifiers.AWS_SES:
            _LOGGER.error('The notifier is not of type %s', Notifiers.AWS_SES)
            raise ValueError(recepient.notifier.value)

        item = recepient.to_entity()
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
