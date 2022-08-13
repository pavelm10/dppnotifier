from abc import ABC, abstractmethod
from typing import List


class Notifier(ABC):
    @abstractmethod
    def notify(self, events: List):
        pass


class GmailNotifier(Notifier):
    def notify(self, events: List):
        pass


class WhatsAppNotifier(Notifier):
    def notify(self, events: List):
        pass
