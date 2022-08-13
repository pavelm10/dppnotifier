from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class TrafficEvent:
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    active: bool
    lines: List[str]
    message: str
    event_id: str
