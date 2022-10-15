import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from dppnotifier.app.dpptypes import TrafficEvent
from dppnotifier.app.utils import localize_datetime, utcnow_localized

_LOGGER = logging.getLogger(__name__)

CURRENT_URL = 'https://pid.cz/mimoradnosti/'
ARCHIVE_URL = 'https://pid.cz/mimoradnosti/?archive=1'


@dataclass
class Search:
    """Search object to parse particular HTML element"""

    _type: str
    _class: Optional[str] = None
    href: Optional[bool] = False

    def find_all(self, elements) -> List:
        return elements.find_all(
            self._type, class_=self._class, href=self.href
        )

    def find(self, elements) -> List:
        return elements.find(self._type, class_=self._class)


@dataclass
class RawContainer:
    """Container for holding raw parsed data

    Parameters
    ----------
    dates : List[str]
        List of events dates
    lines : List[str]
        List of events lines being affected
    messages : List[str]
        List of events messages describing the event
    event_ids : List[str]
        List of events IDs
    urls : List[str]
        List of events URL links
    """

    dates: List[str]
    lines: List[str]
    messages: List[str]
    event_ids: List[str]
    urls: List[str]


def _parse_time(time_str: str) -> Tuple[datetime, Optional[datetime]]:
    """Parses found time string for start and end datetime.

    Parameters
    ----------
    time_str : str
        Time string found

    Returns
    -------
    Tuple[datetime, Optional[datetime]]
        Start datetime and end datetime
    """
    if 'provoz obnoven' in time_str:
        start_str = ''
        end_str = time_str
    else:
        start_str, end_str = time_str.split(' - ')

    start_date = _parse_start_date(start_str)
    end_date = _parse_today_date(end_str)
    return start_date, end_date


def _parse_today_date(time_str: str) -> Optional[datetime]:
    """Tries to parse time string that should be from today date.

    Parameters
    ----------
    time_str : str
        Time string found

    Returns
    -------
    Optional[datetime]
        If parsed returns datetime else None
    """
    today = datetime.today()
    pattern_today = r'[\d]+:[\d]+'
    searched = re.search(pattern_today, time_str)
    time = None
    if searched is not None:
        time = datetime.strptime(searched.group(), '%H:%M')
        time = datetime(
            today.year, today.month, today.day, time.hour, time.minute, 0
        )
        time = localize_datetime(time)
    return time


def _parse_start_date(time_str: str) -> datetime:
    """Parses start date from times string

    Parameters
    ----------
    time_str : str
        Time string to parse

    Returns
    -------
    datetime
        Start datetime
    """
    today = datetime.today()
    pattern_not_today = r'[\d]+.[\d]+. [\d]+:[\d]+'
    searched = re.search(pattern_not_today, time_str)
    if searched is None:
        start_time = _parse_today_date(time_str)
    else:
        time = datetime.strptime(searched.group(), '%d.%m. %H:%M')
        start_time = datetime(
            today.year, time.month, time.day, time.hour, time.minute
        )
        start_time = localize_datetime(start_time)
    return start_time


def _get_events_ids(links: List[str]) -> Tuple[List[str], List[str]]:
    """Parses URL links to get events IDs

    Parameters
    ----------
    links : List[str]
        List of URL links to parse

    Returns
    -------
    Tuple[List[str], List[str]]
        Event IDs and its URL links
    """
    pattern = r'id=[\d]+-[\d]+'
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


def find_events(html_contents: bytes) -> RawContainer:
    """Finds all the events in the HTML contents and parses them.

    Parameters
    ----------
    html_contents : bytes
        Scrapped HTML content

    Returns
    -------
    RawContainer
        Container of parsed data

    Raises
    ------
    ValueError
        If the found elements are not of the same length.
    """
    dates_search = Search('div', 'date')
    lines_search = Search('span', 'lines-single')
    msg_search = Search('td', 'lines-title clickable')
    exceptions_search = Search('table', 'vyluka vyluka-expand vyluky-vymi')
    links_search = Search('a', href=True)

    soup = BeautifulSoup(html_contents, "html.parser")

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

    return RawContainer(
        dates=dates,
        lines=lines,
        messages=messages,
        event_ids=event_ids,
        urls=urls,
    )


def fetch_events(
    html_content: bytes, active_only: bool = False
) -> Iterator[TrafficEvent]:
    """Parses the HTML content and retrieves all the events.

    Parameters
    ----------
    html_content : bytes
        Scrapped HTML content
    active_only : bool, optional
        If only active events shall be returned, by default False

    Yields
    ------
    Iterator[TrafficEvent]
        Iterator of the parsed deserialized traffic events objects.
    """
    now = utcnow_localized()

    raw_data = find_events(html_content)
    dates = raw_data.dates
    lines = raw_data.lines
    messages = raw_data.messages
    event_ids = raw_data.event_ids
    urls = raw_data.urls

    for date, line, message, ev_id, url in zip(
        dates, lines, messages, event_ids, urls
    ):
        date = date.text.replace('\xa0', ' ')
        start_date, end_date = _parse_time(date)
        active = end_date is None or end_date > now

        if active_only and not active:
            continue

        line = line.text.strip().split(', ')
        msg = message.text.strip()
        yield TrafficEvent(
            start_date=start_date,
            end_date=end_date,
            active=active,
            lines=line,
            message=msg,
            event_id=ev_id,
            url=url,
        )


def is_event_active(event_uri: str) -> bool:
    """Scrapes the event web page and checks for terminations signs, if found
    the event is inactive, else is active.

    Parameters
    ----------
    event_uri : str
        The events URL link

    Returns
    -------
    bool
        True if active else False
    """
    res = requests.get(event_uri, timeout=30)
    soup = BeautifulSoup(res.content, 'html.parser')
    results = soup.find(id="st-container")

    content = Search('div', 'content')
    contents = content.find_all(results)
    if len(contents) == 1:
        if 'Požadovaná stránka nebyla nalezena' in contents[0].text:
            return False

    termination = Search('div', 'stops-table-alert')
    terminations = termination.find_all(results)
    if len(terminations) > 0:
        return False
    return True
