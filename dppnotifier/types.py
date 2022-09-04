from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

TIME_FORMAT = '%Y%m%dT%H%M'


class Notifiers(Enum):
    AWS_SES = 'aws-ses'
    WHATSAPP = 'whatsapp'
    LOGGING = 'log'


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
            self_dict['start_date'] = datetime.strftime(
                self.start_date, TIME_FORMAT
            )
        else:
            self_dict['start_date'] = 'NULL'

        if self.end_date is not None:
            self_dict['end_date'] = datetime.strftime(
                self.end_date, TIME_FORMAT
            )
        else:
            self_dict['end_date'] = 'NULL'

        self_dict['active'] = 1 if self.active else 0

        return self_dict

    @classmethod
    def from_entity(cls, entity: Dict[str, str]):
        try:
            start_date = datetime.strptime(entity['start_date'], TIME_FORMAT)
        except (TypeError, ValueError, KeyError):
            start_date = None
        try:
            end_date = datetime.strptime(entity['end_date'], TIME_FORMAT)
        except (TypeError, ValueError, KeyError):
            end_date = None

        return cls(
            start_date=start_date,
            end_date=end_date,
            active=bool(entity['active']),
            lines=entity['lines'],
            message=entity['message'],
            event_id=entity['event_id'],
            url=entity['url'],
        )


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


@dataclass
class NotifierSubscribers:
    notifier: Any
    subscribers: List[Subscriber]
