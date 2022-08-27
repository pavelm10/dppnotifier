import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import boto3
import requests
from botocore.exceptions import ClientError

from dppnotifier.credentials import WhatsAppCredential
from dppnotifier.log import init_logger
from dppnotifier.types import Recepient, TrafficEvent

_LOGGER = init_logger(__name__)


class Notifier(ABC):
    @abstractmethod
    def notify(
        self,
        events: List[TrafficEvent],
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        pass


class AwsSesNotifier(Notifier):
    AWS_REGION = "eu-central-1"
    CHARSET = "UTF-8"
    SUBJECT = "DPP NOTIFICATION"

    def __init__(
        self,
        sender: Optional[str] = 'marpav.py@gmail.com',
        profile: Optional[str] = 'dppnotifier',
    ):
        session = boto3.Session(profile_name=profile)
        self._client = session.client('ses', region_name=self.AWS_REGION)
        self._sender = sender

    def notify(
        self,
        events: List[TrafficEvent],
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        for event in events:
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
                            f'Started: {event.start_date}\n'
                            f'Lines: {event.lines}\n'
                            f'Info: {event.message}\n'
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
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._credential.token}",
            'Content-Type': 'application/json',
        }

    @property
    def _api_url(self) -> str:
        f"https://graph.facebook.com/{self.API_VERSION}/{self._credential.phone_id}/messages"

    def notify(
        self,
        events: List[TrafficEvent],
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        for event in events:
            for sub in recepient_list:
                data = {
                    'messaging_product': 'whatsapp',
                    'to': sub.uri,
                    'type': 'text',
                    'text': {
                        'preview_url': False,
                        'body': (
                            f'Start time: {event.start_date}\n'
                            f'Message: {event.message}\n'
                            f'Lines: {event.lines}\n'
                            f'URL: https://pid.cz/mimoradnost/?id={event.event_id}\n'
                        ),
                    },
                }
                response = requests.post(
                    self._api_url, headers=self._headers, data=json.dumps(data)
                )
                if not response.ok:
                    _LOGGER.error(response.text)


class LogNotifier(Notifier):
    def notify(
        self,
        events: List[TrafficEvent],
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        for ev in events:
            _LOGGER.info(
                'Event %s, started: %s, ended: %s. Affected lines: %s. %s',
                ev.event_id,
                ev.start_date,
                ev.end_date,
                ev.lines,
                ev.message,
            )
