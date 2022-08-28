import json
import os
from abc import ABC, abstractmethod, abstractproperty
from pathlib import Path
from typing import Dict, Optional, Tuple

import boto3
import requests
from botocore.exceptions import ClientError

from dppnotifier.credentials import WhatsAppCredential
from dppnotifier.log import init_logger
from dppnotifier.types import Notifiers, Recepient, TrafficEvent

_LOGGER = init_logger(__name__)


class Notifier(ABC):
    NOTIFIER_TYPE = None

    @abstractmethod
    def notify(
        self,
        event: TrafficEvent,
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        pass

    @abstractproperty
    def enabled(self) -> bool:
        pass


class AwsSesNotifier(Notifier):
    AWS_REGION = "eu-central-1"
    CHARSET = "UTF-8"
    SUBJECT = "DPP NOTIFICATION"
    NOTIFIER_TYPE = Notifiers.AWS_SES

    def __init__(
        self,
        sender: Optional[str] = 'marpav.py@gmail.com',
        profile: Optional[str] = 'dppnotifier',
    ):
        session = boto3.Session(profile_name=profile)
        self._client = session.client('ses', region_name=self.AWS_REGION)
        self._sender = sender
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def notify(
        self,
        event: TrafficEvent,
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        try:
            response = self._send_email(event, recepient_list)
        except ClientError as error:
            _LOGGER.error('An error occurred %s', error)
        else:
            _LOGGER.info('Email sent: %s', response['MessageId'])

    def _send_email(
        self,
        event: TrafficEvent,
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        response = self._client.send_email(
            Destination={
                'ToAddresses': [r.uri for r in recepient_list],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': self.CHARSET,
                        'Data': (
                            f'Start time: {event.start_date}\n'
                            f'Message: {event.message}\n'
                            f'Lines: {event.lines}\n'
                            f'URL: {event.url}\n'
                        ),
                    },
                },
                'Subject': {
                    'Charset': self.CHARSET,
                    'Data': self.SUBJECT,
                },
            },
            Source=self._sender,
        )
        return response


class WhatsAppNotifier(Notifier):
    API_VERSION = 'v13.0'
    NOTIFIER_TYPE = Notifiers.WHATSAPP

    def __init__(self, credential: Optional[WhatsAppCredential] = None):
        cred_path = os.getenv('WHATSAPP_CRED_PATH')
        if cred_path is not None and credential is None:
            self._credential = WhatsAppCredential.from_file(Path(cred_path))
        else:
            self._credential = credential

        self._enabled = False
        if self._credential is not None:
            self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def notifier_type(self) -> Notifiers:
        return Notifiers.WHATSAPP

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._credential.token}",
            'Content-Type': 'application/json',
        }

    @property
    def _api_url(self) -> str:
        return f"https://graph.facebook.com/{self.API_VERSION}/{self._credential.phone_id}/messages"

    def notify(
        self,
        event: TrafficEvent,
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        for sub in recepient_list:
            data = {
                'messaging_product': 'whatsapp',
                'recipient_type': "individual",
                'to': sub.uri,
                'type': 'template',
                "template": {
                    "name": "dppnotification",
                    "language": {"code": "en_US"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": event.message},
                                {"type": "text", "text": event.start_date},
                                {"type": "text", "text": event.lines},
                                {"type": "text", "text": event.url},
                            ],
                        }
                    ],
                },
            }

            response = requests.post(
                self._api_url, headers=self._headers, data=json.dumps(data)
            )
            if not response.ok:
                _LOGGER.error(response.text)
            else:
                _LOGGER.info('Whatsapp message sent')
