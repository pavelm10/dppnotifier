from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from dppnotifier.app.utils import utcnow_localized


class Notifiers(Enum):
    """Notifiers types"""

    AWS_SES = 'aws-ses'
    WHATSAPP = 'whatsapp'
    LOGGING = 'log'
    TELEGRAM = 'telegram'


@dataclass
class TrafficEvent:
    """The traffic event

    Parameters
    ----------
    active : bool
        Indicator whether the event is still active or not
    lines : List[str]
        List of lines affected by the event
    message : str
        The event message
    event_id : str
        The event ID
    url : str
        The URL link to the event
    start_date : Optional[datetime]
        The event start datetime
    end_date : Optional[datetime]
        The event end datetime
    """

    active: bool
    lines: List[str]
    message: str
    event_id: str
    url: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def to_entity(self) -> Dict:
        """Serializes the event object to the entity.

        Returns
        -------
        Dict
            The entity
        """
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
        self_dict['updated'] = utcnow_localized().isoformat()

        return self_dict

    @classmethod
    def from_entity(cls, entity: Dict[str, Any]) -> TrafficEvent:
        """Deserializes the entity to the event object.

        Parameters
        ----------
        entity : Dict[str, Any]
            The traffic event entity to deserialize

        Returns
        -------
        TrafficEvent
            The deserialized event
        """
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
        """Generates notification message from the event."""
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
        """Generates logging message of the event."""
        started = self.start_date
        if started is not None:
            started = started.isoformat()
        else:
            started = 'unknown'
        return f'Started {started}, URL: {self.url}'

    def __eq__(self, other: TrafficEvent) -> bool:
        """Implemented to be able to compare to events objects.

        Parameters
        ----------
        other : TrafficEvent
            Other traffic event to compare with

        Returns
        -------
        bool
            True ff the events are the same, else False
        """
        if other is None or not isinstance(other, TrafficEvent):
            return False
        self_dict = self.to_entity()
        other_dict = other.to_entity()
        del self_dict['updated']
        del other_dict['updated']
        return self_dict == other_dict


@dataclass
class Subscriber:
    """The subscriber object

    Parameters
    ----------
    notifier : Notifiers
        The notifier type the subscriber wants the notification from
    uri : str
        The identifier of the subscriber, e.g. email, phone number, etc.
    user : str
        The user name
    lines : Optional[Tuple[str]] = ()
        The lines that the user wants to receive notifications for if the line
        is affected by an event.
    """

    notifier: Notifiers
    uri: str
    user: str
    lines: Optional[Tuple[str]] = ()

    def to_entity(self) -> Dict[str, Any]:
        """Serializes the subscriber object.

        Returns
        -------
        Dict[str, Any]
            Serialized subscriber
        """
        entity = asdict(self)
        entity['notifier'] = self.notifier.value
        entity['lines'] = ','.join(self.lines)
        return entity

    @classmethod
    def from_entity(cls, entity: Dict[str, str]) -> Subscriber:
        """Deserializes the subscriber entity to the object.

        Parameters
        ----------
        entity : Dict[str, str]
            The subscriber entity to deserialize

        Returns
        -------
        Subscriber
            The deserialized subscriber object
        """
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
    """Container of holding notifier object and its subscribers"""

    notifier: Any
    subscribers: List[Subscriber]
