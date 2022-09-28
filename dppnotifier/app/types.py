from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class Notifiers(Enum):
    AWS_SES = 'aws-ses'
    WHATSAPP = 'whatsapp'
    LOGGING = 'log'
    TELEGRAM = 'telegram'


@dataclass
class TrafficEvent:
    active: bool
    lines: List[str]
    message: str
    event_id: str
    url: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def to_entity(self) -> Dict:
        self_dict = asdict(self)

        if self.start_date is not None:
            self_dict['start_date'] = self.start_date.isoformat()
        else:
            self_dict['start_date'] = 'NULL'

        if self.end_date is not None:
            self_dict['end_date'] = self.end_date.isoformat()
        else:
            self_dict['end_date'] = 'NULL'

        self_dict['active'] = 1 if self.active else 0

        return self_dict

    @classmethod
    def from_entity(cls, entity: Dict[str, str]):
        try:
            start_date = datetime.fromisoformat(entity['start_date'])
        except (TypeError, ValueError, KeyError):
            start_date = None
        try:
            end_date = datetime.fromisoformat(entity['end_date'])
        except (TypeError, ValueError, KeyError):
            end_date = None

        return cls(
            start_date=start_date,
            end_date=end_date,
            active=bool(entity['active']),
            lines=entity.get('lines', []),
            message=entity['message'],
            event_id=entity['event_id'],
            url=entity['url'],
        )

    def to_message(self) -> str:
        start_date = self.start_date
        if start_date is not None:
            start_date = start_date.isoformat()

        return (
            f'Start time: {start_date}\n'
            f'Message: {self.message}\n'
            f'Lines: {",".join(self.lines)}\n'
            f'URL: {self.url}\n'
        )

    def to_log_message(self) -> str:
        started = self.start_date
        if started is not None:
            started = started.isoformat()
        else:
            started = 'unknown'
        return f'Started {started}, URL: {self.url}'

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        return self.to_entity() == other.to_entity()


@dataclass
class Subscriber:
    notifier: Notifiers
    uri: str
    user: str
    lines: Optional[Tuple[str]] = ()

    def to_entity(self) -> Dict[str, str]:
        entity = asdict(self)
        entity['notifier'] = self.notifier.value
        entity['lines'] = ','.join(self.lines)
        return entity

    @classmethod
    def from_entity(cls, entity: Dict[str, str]):
        lines = entity.get('lines', ())
        if len(lines) > 0:
            lines = lines.split(',')

        return cls(
            notifier=Notifiers(entity['notifier']),
            uri=entity['uri'],
            user=entity['user'],
            lines=lines,
        )

    def __repr__(self) -> str:
        return f'{self.notifier}, {self.user}, {self.uri}, {self.lines}'


@dataclass
class NotifierSubscribers:
    notifier: Any
    subscribers: List[Subscriber]
