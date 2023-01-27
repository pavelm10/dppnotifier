import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from dppnotifier.app.parser import fetch_events

TEST_DATA_DIR = Path(__file__).parent / 'data'


def get_reference_events(file_path):
    with file_path.open('r') as fo:
        data = json.load(fo)
        for event in data.values():
            event['start_date'] = event['start_date'].split('+')[0]
            event['end_date'] = event['end_date'].split('+')[0]
            try:
                del event['updated']
                del event['active']
            except KeyError:
                pass
        return data


def get_events(html_path):
    today = datetime.today().date()
    with html_path.open('rb') as fo:
        events = {}
        for event in fetch_events(fo):
            ev = event.to_entity()
            if ev['start_date'] != 'NULL':
                sd = datetime.fromisoformat(ev['start_date'])
                start_date = sd.date()
                if start_date == today:
                    ev['start_date'] = 'today'
                else:
                    sd -= timedelta(days=365)
                    ev['start_date'] = sd.isoformat().split('+')[0]
            if ev['end_date'] != 'NULL':
                ed = datetime.fromisoformat(ev['end_date'])
                event_date = ed.date()
                if event_date == today:
                    ev['end_date'] = 'today'
                else:
                    ed -= timedelta(days=365)
                    ev['end_date'] = ed.isoformat().split('+')[0]
            try:
                del ev['updated']
                del ev['active']
            except KeyError:
                pass
            events[event.event_id] = ev
        return events


@pytest.mark.parametrize('file', (list(TEST_DATA_DIR.glob('*.html'))))
def test_parser_on_data(file):
    meta_file = file.with_suffix('.json')
    reference = get_reference_events(meta_file)
    events = get_events(file)
    for eid, ref_event in reference.items():
        event = events[eid]
        assert event == ref_event
