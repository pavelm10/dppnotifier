from abc import ABC, abstractmethod
from typing import List

from dppnotifier.log import init_logger
from dppnotifier.types import TrafficEvent

_LOGGER = init_logger(__name__)


class Notifier(ABC):
    @abstractmethod
    def notify(self, events: List[TrafficEvent]):
        pass


class GmailNotifier(Notifier):
    def notify(self, events: List[TrafficEvent]):
        pass


class WhatsAppNotifier(Notifier):
    def notify(self, events: List[TrafficEvent]):
        pass


class LogNotifier(Notifier):
    def notify(self, events: List[TrafficEvent]):
        for ev in events:
            _LOGGER.info(
                'Event %s, started: %s. Affected lines: %s. %s',
                ev.event_id,
                ev.start_date,
                ev.lines,
                ev.message,
            )
