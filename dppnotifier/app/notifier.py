import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import boto3
import requests
from botocore.exceptions import ClientError

from dppnotifier.app.constants import AWS_REGION
from dppnotifier.app.credentials import TelegramCredential, WhatsAppCredential
from dppnotifier.app.dpptypes import Notifiers, Subscriber, TrafficEvent

_LOGGER = logging.getLogger(__name__)


class Notifier(ABC):
    """Notifier interface class"""

    NOTIFIER_TYPE = None

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        pass

    @abstractmethod
    def notify(self, event: TrafficEvent, subscribers: Tuple[Subscriber]):
        pass

    @property
    def enabled(self) -> bool:
        return False


class AwsSesNotifier(Notifier):
    """AWS SES notifier which sends emails. It's the default notifier
    hence must be always initialized, i.e. AWS_SENDER_EMAIL env.var. must
    be provided.
    """

    CHARSET = "UTF-8"
    SUBJECT = "DPP NOTIFICATION"
    NOTIFIER_TYPE = Notifiers.AWS_SES

    def __init__(self):
        profile = os.environ.get('AWS_PROFILE')
        self._sender = os.environ['AWS_SENDER_EMAIL']
        session = boto3.Session(profile_name=profile)
        self._client = session.client('ses', region_name=AWS_REGION)
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def notify(self, event: TrafficEvent, subscribers: Tuple[Subscriber]):
        """Sends email to all the subscribers for the given event.

        Parameters
        ----------
        event : TrafficEvent
            The event to be sent
        subscribers : Tuple[Subscriber]
            The subscribers to be notified
        """
        if len(subscribers) == 0:
            return

        try:
            self.send_email(event, subscribers)
        except ClientError as error:
            _LOGGER.error('An error occurred %s', error)
        else:
            _LOGGER.info('Email sent')

    def send_email(
        self,
        event: TrafficEvent,
        subscribers: Tuple[Subscriber],
    ):
        """Main method that send email to all the subscribers for the given
        event.

        Parameters
        ----------
        event : TrafficEvent
            The event to be sent
        subscribers : Tuple[Subscriber]
            The subscribers to be notified
        """
        self._client.send_email(
            Destination={
                'ToAddresses': [r.uri for r in subscribers],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': self.CHARSET,
                        'Data': event.to_message(),
                    },
                },
                'Subject': {
                    'Charset': self.CHARSET,
                    'Data': self.SUBJECT,
                },
            },
            Source=self._sender,
        )


class WhatsAppNotifier(Notifier):
    """WhatsApp notifier that sends messages to the WhatsApp"""

    API_VERSION = 'v13.0'
    NOTIFIER_TYPE = Notifiers.WHATSAPP

    def __init__(self, credential: Optional[WhatsAppCredential] = None):
        cred_path = os.getenv('WHATSAPP_CRED_PATH')
        self._template_name = os.getenv('WHATSAPP_TEMPLATE', 'dppnotification')
        if cred_path is not None and credential is None:
            self._credential = WhatsAppCredential.from_file(Path(cred_path))
        else:
            self._credential = credential

        self._enabled = False
        if self._credential is not None:
            self._enabled = True

        self._session = None

    def __enter__(self):
        self._session = requests.Session()
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if self._session is not None:
            self._session.close()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def _headers(self) -> Dict[str, str]:
        if self._credential is None:
            raise ValueError('Credential not defined')

        return {
            "Authorization": f"Bearer {self._credential.token}",
            'Content-Type': 'application/json',
        }

    @property
    def _api_url(self) -> str:
        if self._credential is None:
            raise ValueError('Credential not defined')
        return f'https://graph.facebook.com/{self.API_VERSION}/{self._credential.phone_id}/messages'

    def notify(self, event: TrafficEvent, subscribers: Tuple[Subscriber]):
        """For each subscriber sends the WhatsApp message about the event.

        Parameters
        ----------
        event : TrafficEvent
            The event to be sent
        subscribers : Tuple[Subscriber]
            The subscribers to be notified
        """
        for sub in subscribers:
            self.send_message(event, sub)

    def send_message(self, event: TrafficEvent, subscriber: Subscriber):
        """Sends the WhatsApp message about the event.

        Parameters
        ----------
        event : TrafficEvent
            The event to be sent
        subscriber : Subscriber
            The subscriber to be notified

        Raises
        ------
        NotifierNotInitialized
            When a method of notifier is not called under its context manager
        """
        if self._session is None:
            raise NotifierNotInitialized()

        data = self._build_message(event=event, subscriber=subscriber)
        response = self._session.post(
            self._api_url,
            headers=self._headers,
            data=json.dumps(data),
            timeout=10,
        )
        if not response.ok:
            _LOGGER.error(response.text)
        else:
            _LOGGER.info('Whatsapp message sent')

    def _build_message(
        self, event: TrafficEvent, subscriber: Subscriber
    ) -> Dict[str, Any]:
        """Builds the event message.

        Parameters
        ----------
        event : TrafficEvent
            The event to be sent
        subscribers : Subscriber
            The subscriber to be notified

        Returns
        -------
        Dict[str, Any]
            The deserialized event message
        """
        start_date = event.start_date
        if start_date is not None:
            start_date = start_date.isoformat()
        else:
            start_date = 'Unknown'

        data = {
            'messaging_product': 'whatsapp',
            'recipient_type': "individual",
            'to': subscriber.uri,
            'type': 'template',
            "template": {
                "name": self._template_name,
                "language": {"code": "en_US"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": event.message},
                            {
                                "type": "text",
                                "text": start_date,
                            },
                            {
                                "type": "text",
                                "text": ','.join(event.lines),
                            },
                            {"type": "text", "text": event.url},
                        ],
                    }
                ],
            },
        }
        return data


class TelegramNotifier(Notifier):
    """Telegram notifier that sends telegram messages."""

    NOTIFIER_TYPE = Notifiers.TELEGRAM

    def __init__(self, credential: Optional[TelegramCredential] = None):
        cred_path = os.getenv('TELEGRAM_CRED_PATH')
        if cred_path is not None and credential is None:
            self._credential = TelegramCredential.from_file(Path(cred_path))
        else:
            self._credential = credential

        self._enabled = False
        if self._credential is not None:
            self._enabled = True

        self._session = None

    def __enter__(self):
        self._session = requests.Session()
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if self._session is not None:
            self._session.close()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def _api_url(self) -> Optional[str]:
        if self._credential is not None:
            return f'https://api.telegram.org/bot{self._credential.token}/sendMessage'
        return None

    def _send_message(
        self, message: str, uri: Union[str, int]
    ) -> requests.Response:
        """Low level method for sending Telegram message.

        Parameters
        ----------
        message : str
            Message to send
        uri : Union[str, int]
            Telegram chat_id

        Returns
        -------
        requests.Response
            Server response

        Raises
        ------
        NotifierNotInitialized
            When a method of notifier is not called under its context manager
        TelegramError
            When Telegram API returns error code larger or equal 400
        """
        if self._session is None:
            raise NotifierNotInitialized()

        url = f"{self._api_url}?chat_id={int(uri)}&text={message}"
        res = self._session.get(url, timeout=10)
        if res.status_code >= 200:
            raise TelegramError(f'{res.status_code} - {res.text}')
        return res


class EventTelegramNotifier(TelegramNotifier):
    """Telegram notifier that sends telegram messages about the events."""

    def send_message(self, event: TrafficEvent, subscriber: Subscriber):
        """Sends the Telegram message about the event.

        Parameters
        ----------
        event : TrafficEvent
            The event to be sent
        subscriber : Subscriber
            The subscriber to be notified
        """
        message = event.to_message()
        try:
            self._send_message(message=message, uri=subscriber.uri)
        except TelegramError as exc:
            _LOGGER.error(exc.args[0])
            return
        else:
            _LOGGER.info('Telegram message sent')

    def notify(self, event: TrafficEvent, subscribers: Tuple[Subscriber]):
        """For each subscriber sends the WhatsApp message about the event.

        Parameters
        ----------
        event : TrafficEvent
            The event to be sent
        subscribers : Tuple[Subscriber]
            The subscribers to be notified
        """
        for sub in subscribers:
            self.send_message(event, sub)


class AlertTelegramNotifier(TelegramNotifier):
    """Telegram notifier that sends telegram messages about the processing
    alerts."""

    def __init__(self, alert_subscriber_uri: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.alert_subscriber_uri = alert_subscriber_uri

    @property
    def enabled(self) -> bool:
        return super().enabled and self.alert_subscriber_uri is not None

    def send_alert(self, alert: str):
        """Sends the Telegram message about the alert.

        Parameters
        ----------
        alert : str
            The alert to be sent
        """
        if not self.enabled:
            _LOGGER.info('Alert notifier not enabled')
            return
        try:
            self._send_message(message=alert, uri=self.alert_subscriber_uri)
        except TelegramError as exc:
            _LOGGER.error(exc.args[0])
            return
        else:
            _LOGGER.warning('Telegram alert message sent')

    def notify(self, event: TrafficEvent, subscribers: Tuple[Subscriber]):
        raise NotImplementedError()


class NotifierNotInitialized(Exception):
    """When a method of notifier is not called under its context manager"""


class TelegramError(Exception):
    """When Telegram API returns error code larger or equal 400"""
