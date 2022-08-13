# TODO: class to store traffic events to NoSQL database and is also able to
# update its active state. It is needed for notifier so that it is known,
# which event was already notified or not.

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from dppnotifier.log import init_logger
from dppnotifier.types import TrafficEvent

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
        self.db[event.event_id] = event.to_dict()
        self._dump()
