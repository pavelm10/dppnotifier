from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class TrafficEvent:
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    active: bool
    lines: List[str]
    message: str
    event_id: str

    def to_dict(self) -> Dict:
        start_date = self.start_date
        if start_date is not None:
            start_date = datetime.strftime(start_date, '%Y%m%dT%H%M')

        end_date = self.end_date
        if end_date is not None:
            end_date = datetime.strftime(end_date, '%Y%m%dT%H%M')

        self_dict = asdict(self)
        self_dict['start_date'] = start_date
        self_dict['end_date'] = end_date
        return self_dict


@dataclass
class Recepient:
    uri: str
