# TODO: class to store traffic events to NoSQL database and is also able to
# update its active state. It is needed for notifier so that it is known,
# which event was already notified or not.

import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from dppnotifier.types import TrafficEvent


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
        self.db = self._load()

    def _load(self):
        if not self._file_path.exists():
            self.db = {}
            return

        with open(self._file_path, 'r') as file:
            self.db = json.load(file)

    def _dump(self):
        with open(self._file_path, 'w') as file:
            json.dump(self.db, file)

    def find_by_id(self, event_id: str) -> Optional[TrafficEvent]:
        event = self.db.get(event_id)
        if event is not None:
            event = TrafficEvent(**event)
        return event

    def upsert_event(self, event: TrafficEvent):
        self.db[event.event_id] = asdict(event)
        self._dump()
