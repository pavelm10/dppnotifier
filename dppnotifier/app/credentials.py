from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WhatsAppCredential:
    """WhatsApp credential handler"""

    token: str
    phone_id: str
    account_id: str

    @classmethod
    def from_file(cls, credential_path: Path) -> WhatsAppCredential:
        """Initializes the credential from the credential file.

        Parameters
        ----------
        credential_path : Path
            Path to the credential file

        Returns
        -------
        WhatsAppCredential
            The credential handler
        """
        with credential_path.open('r', encoding='utf-8') as file:
            data = json.load(file)
            return cls(
                token=data['token'],
                phone_id=data['phone_id'],
                account_id=data['account_id'],
            )


@dataclass
class TelegramCredential:
    """Telegram credential handler"""

    token: str
    name: str

    @classmethod
    def from_file(cls, credential_path: Path) -> TelegramCredential:
        """Initializes the credential from the credential file.

        Parameters
        ----------
        credential_path : Path
           Path to the credential file

        Returns
        -------
        TelegramCredential
            The credential handler
        """
        with credential_path.open('r', encoding='utf-8') as file:
            data = json.load(file)
            return cls(
                token=data['token'],
                name=data['name'],
            )
