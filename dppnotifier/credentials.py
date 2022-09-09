import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WhatsAppCredential:
    token: str
    phone_id: str
    account_id: str

    @classmethod
    def from_file(cls, credential_path: Path):
        with credential_path.open('r', encoding='utf-8') as file:
            data = json.load(file)
            return cls(
                token=data['token'],
                phone_id=data['phone_id'],
                account_id=data['account_id'],
            )


@dataclass
class TelegramCredential:
    token: str
    name: str

    @classmethod
    def from_file(cls, credential_path: Path):
        with credential_path.open('r', encoding='utf-8') as file:
            data = json.load(file)
            return cls(
                token=data['token'],
                name=data['name'],
            )
