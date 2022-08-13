from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

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
        profile: Optional[str] = 'ddpnotifier',
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
    def notify(
        self,
        events: List[TrafficEvent],
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        pass


class LogNotifier(Notifier):
    def notify(
        self,
        events: List[TrafficEvent],
        recepient_list: Optional[Tuple[Recepient]] = (),
    ):
        for ev in events:
            _LOGGER.info(
                'Event %s, started: %s. Affected lines: %s. %s',
                ev.event_id,
                ev.start_date,
                ev.lines,
                ev.message,
            )
