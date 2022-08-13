import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

CURRENT_URL = 'https://pid.cz/mimoradnosti/'
ARCHIVE_URL = 'https://pid.cz/mimoradnosti/?archive=1'


@dataclass
class TrafficEvent:
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    active: bool
    lines: List[str]
    message: str
    event_id: str


@dataclass
class Search:
    _type: str
    _class: str

    def find_all(self, elements) -> List:
        return elements.find_all(self._type, class_=self._class)

    def find(self, elements) -> List:
        return elements.find(self._type, class_=self._class)


def _parse_time(time_str: str) -> Tuple[datetime, Optional[datetime]]:
    try:
        start_str, end_str = time_str.split(' - ')
    except ValueError:
        # in case of: time_str = 'provoz obnoven: dnes xx:xx'
        start_str = ''
        end_str = time_str
    start_date = _parse_start_date(start_str)
    end_date = _parse_today_date(end_str)
    return start_date, end_date


def _parse_today_date(time_str: str) -> Optional[datetime]:
    today = datetime.today()
    pattern_today = '[\d]+:[\d]+'
    searched = re.search(pattern_today, time_str)
    time = None
    if searched is not None:
        time = datetime.strptime(searched.group(), '%H:%M')
        time = datetime(
            today.year, today.month, today.day, time.hour, time.minute
        )
    return time


def _parse_start_date(time_str: str) -> datetime:
    today = datetime.today()
    pattern_not_today = '[\d]+.[\d]+. [\d]+:[\d]+'
    searched = re.search(pattern_not_today, time_str)
    if searched is None:
        start_time = _parse_today_date(time_str)
    else:
        time = datetime.strptime(searched.group(), '%d.%m. %H:%M')
        start_time = datetime(
            today.year, time.month, time.day, time.hour, time.minute
        )
    return start_time


def _create_event_hash(
    start_date: Optional[datetime], lines: List[str], message: str
) -> str:
    time_str = ''
    if isinstance(start_date, datetime):
        time_str = start_date.strftime('%Y%M%dT%H%m')
    line_str = ','.join(lines)
    str_to_hash = time_str + line_str + message
    hashed = hashlib.sha1(str_to_hash.encode("utf-8")).hexdigest()
    return hashed


def fetch_events(active_only: bool = False) -> List[TrafficEvent]:
    dates_search = Search('div', 'date')
    lines_search = Search('span', 'lines-single')
    msg_search = Search('td', 'lines-title clickable')
    exceptions_search = Search('table', 'vyluka vyluka-expand vyluky-vymi')

    page = requests.get(CURRENT_URL)
    soup = BeautifulSoup(page.content, "html.parser")

    results = soup.find(id="st-container")
    exception_elements = exceptions_search.find(results)

    dates = dates_search.find_all(exception_elements)
    lines = lines_search.find_all(exception_elements)
    messages = msg_search.find_all(exception_elements)

    issues = []
    for date, line, message in zip(dates, lines, messages):
        date = date.text.strip()
        start_date, end_date = _parse_time(date)
        active = end_date is None

        if active_only and not active:
            continue

        line = line.text.strip().split(', ')
        msg = message.text.strip()
        ev_id = _create_event_hash(
            start_date=start_date, lines=line, message=msg
        )
        issue = TrafficEvent(
            start_date=start_date,
            end_date=end_date,
            active=active,
            lines=line,
            message=msg,
            event_id=ev_id,
        )
        issues.append(issue)

    return issues
