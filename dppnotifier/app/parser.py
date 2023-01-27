import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from bs4 import BeautifulSoup, ResultSet, element

from dppnotifier.app.dpptypes import TrafficEvent
from dppnotifier.app.utils import localize_datetime, utcnow_localized


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


def _parse_time(
    time_str: str,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Parses found time string for start and end datetime.

    Parameters
    ----------
    time_str : str
        Time string found

    Returns
    -------
    Tuple[Optional[datetime], Optional[datetime]]
        Start datetime and end datetime
    """
    if 'provoz obnoven' in time_str:
        start_str = ''
        end_str = time_str
    else:
        try:
            start_str, end_str = time_str.split(' - ')
        except ValueError as exc:
            if 'dnes' in time_str:
                start_str = re.search(r'\d{1,2}:\d{2}', time_str)
                if start_str is None:
                    # pylint: disable=raise-missing-from
                    raise ParserError(f'Cannot parse {time_str}')
                start_str = start_str.group()
                end_str = ''
            else:
                raise ParserError(f'Cannot parse {time_str}') from exc

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


def _parse_start_date(time_str: str) -> Optional[datetime]:
    """Parses start date from times string

    Parameters
    ----------
    time_str : str
        Time string to parse

    Returns
    -------
    Optional[datetime]
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


def get_raw_events(links: List[ResultSet]) -> Dict[str, Any]:
    """Gets raw events from the list of links tags

    Parameters
    ----------
    links : List[ResultSet]
        Links tags

    Returns
    -------
    Dict[str, Any]
        Raw events

    Raises
    ------
    ParserError
        When the tag text is None
    ParserError
        When no expected content was in at least one link tag
    """
    events = {}
    for tag in links:
        key = tag['href']
        raw_text = tag.text
        if raw_text is None:
            raise ParserError(f'No text in the tag for {key}')

        if key not in events:
            events[key] = {
                'datetime': None,
                'lines': None,
                'text': None,
                'id': _get_event_id(key),
            }

        date_tag = tag.find('div', {'class': ['date']})
        if date_tag:
            events[key]['datetime'] = date_tag.text
            continue

        lines_tag = tag.find('span', {'class': ['lines-single']})
        if lines_tag:
            events[key]['lines'] = lines_tag.text
            continue

        if isinstance(tag.contents[0], element.NavigableString):
            events[key]['text'] = raw_text
            continue

        raise ParserError(f'Failed to get raw events at parsing {key}')
    return events


def _get_event_id(link: str) -> str:
    """Parses URL link to get event's ID

    Parameters
    ----------
    link : str
        ahref link of the event

    Returns
    -------
    str
        Event ID

    Raises
    ------
    ParserError
        When event's ID could not be extracted
    """
    pattern = r'id=[\d]+-[\d]+'
    searched = re.search(pattern, link)
    if searched is None:
        raise ParserError(f'ID not present in link {link}')
    idx = searched.group()[3:]  # strip `id=` string
    return idx


def find_events(html_contents: bytes) -> Dict[str, Any]:
    """Finds all the events in the HTML contents and parses them.

    Parameters
    ----------
    html_contents : bytes
        Scrapped HTML content

    Returns
    -------
    Dict[str, Any]
        Dictionary of raw events data
    """
    exceptions_search = Search('table', 'vyluka vyluka-expand vyluky-vymi')
    links_search = Search('a', href=True)

    soup = BeautifulSoup(html_contents, "html.parser")

    results = soup.find(id="st-container")
    exception_elements = exceptions_search.find(results)
    links = links_search.find_all(exception_elements)
    raw_events = get_raw_events(links)
    return raw_events


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

    raw_events = find_events(html_content)

    for link, event in raw_events.items():
        date = event['datetime'].replace('\xa0', ' ')
        start_date, end_date = _parse_time(date)
        active = end_date is None or end_date > now

        if active_only and not active:
            continue

        line = event['lines'].strip().split(', ')
        msg = event['text'].strip()
        yield TrafficEvent(
            start_date=start_date,
            end_date=end_date,
            active=active,
            lines=line,
            message=msg,
            event_id=event['id'],
            url=link,
        )


def is_event_active(html_content: bytes) -> bool:
    """Scrapes the event web page and checks for terminations signs, if found
    the event is inactive, else is active.

    Parameters
    ----------
    html_content : bytes
        The events web page HTML content

    Returns
    -------
    bool
        True if active else False
    """
    soup = BeautifulSoup(html_content, 'html.parser')
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


class ParserError(Exception):
    """Parsing error occurred"""
