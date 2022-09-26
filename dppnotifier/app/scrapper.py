import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from dppnotifier.app.types import TrafficEvent

_LOGGER = logging.getLogger(__name__)
CURRENT_URL = 'https://pid.cz/mimoradnosti/'
ARCHIVE_URL = 'https://pid.cz/mimoradnosti/?archive=1'


@dataclass
class Search:
    _type: str
    _class: Optional[str] = None
    href: Optional[bool] = False

    def find_all(self, elements) -> List:
        return elements.find_all(
            self._type, class_=self._class, href=self.href
        )

    def find(self, elements) -> List:
        return elements.find(self._type, class_=self._class)


def _parse_time(time_str: str) -> Tuple[datetime, Optional[datetime]]:
    if 'provoz obnoven' in time_str:
        start_str = ''
        end_str = time_str
    else:
        start_str, end_str = time_str.split(' - ')

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


def _get_events_ids(links: List[str]) -> Tuple[List[str], List[str]]:
    pattern = 'id=[\d]+-[\d]+'
    links_list = [l['href'] for l in links]
    ids = []
    urls = []
    for link in links_list:
        searched = re.search(pattern, link)
        assert searched is not None
        idx = searched.group()[3:]  # strip `id=` string
        if idx not in ids:
            ids.append(idx)
            urls.append(link)
    return ids, urls


def fetch_events(active_only: bool = False) -> Iterator[TrafficEvent]:
    now = datetime.now()
    dates_search = Search('div', 'date')
    lines_search = Search('span', 'lines-single')
    msg_search = Search('td', 'lines-title clickable')
    exceptions_search = Search('table', 'vyluka vyluka-expand vyluky-vymi')
    links_search = Search('a', href=True)

    page = requests.get(CURRENT_URL)
    soup = BeautifulSoup(page.content, "html.parser")

    results = soup.find(id="st-container")
    exception_elements = exceptions_search.find(results)

    dates = dates_search.find_all(exception_elements)
    lines = lines_search.find_all(exception_elements)
    messages = msg_search.find_all(exception_elements)
    links = links_search.find_all(exception_elements)
    event_ids, urls = _get_events_ids(links)

    # check all list are of the same length
    base_length = len(dates)
    for list_ in [lines, messages, event_ids, urls]:
        if len(list_) != base_length:
            _LOGGER.error('The elements are not of the same length')
            raise ValueError(f'{len(list_)} != {base_length}')

    for date, line, message, ev_id, url in zip(
        dates, lines, messages, event_ids, urls
    ):
        date = date.text.replace(u'\xa0', u' ')
        start_date, end_date = _parse_time(date)
        active = end_date is None or end_date > now

        if active_only and not active:
            continue

        line = line.text.strip().split(', ')
        msg = message.text.strip()
        issue = TrafficEvent(
            start_date=start_date,
            end_date=end_date,
            active=active,
            lines=line,
            message=msg,
            event_id=ev_id,
            url=url,
        )
        yield issue