from copy import deepcopy

import pytest

from dppnotifier.app import app
from dppnotifier.app.dpptypes import TrafficEvent
from tests.common import DynamoSubscribersDbMock, DynamoTrafficEventsDbMock

EVENT_A = TrafficEvent(
    active=True,
    lines=['A', '7', 'S3', '136', '16'],
    message='message',
    event_id='eidA',
    url='url',
)

EVENT_B = TrafficEvent(
    active=True,
    lines=['17', 'B'],
    message='message',
    event_id='eidB',
    url='url',
)

EVENT_C = TrafficEvent(
    active=True,
    lines=['C'],
    message='message',
    event_id='eidC',
    url='url',
)


@pytest.fixture
def job_mock(mocker):
    events_db_mock = mocker.patch.object(
        app, 'DynamoTrafficEventsDb', autospec=True
    )

    mocker.patch.object(
        app, 'scrape', autospec=True, return_value=b'html-content'
    )

    fetch_events_mock = mocker.patch.object(app, 'fetch_events', autospec=True)
    fetch_events_mock.return_value = [EVENT_A, EVENT_B]

    update_db_mock = mocker.patch.object(app, 'update_db', autospec=True)
    mocker.patch.object(app, 'build_notifiers', autospec=True, return_value=[])
    notify_mock = mocker.patch.object(app, 'notify', autospec=True)

    return events_db_mock, update_db_mock, notify_mock, fetch_events_mock


def test_handle_active_event_failed_scrape(mocker):
    mocker.patch.object(app, 'scrape', autospec=True, return_value=None)
    update_db_mock = mocker.patch.object(app, 'update_db', autospec=True)
    is_active_mock = mocker.patch.object(app, 'is_event_active', autospec=True)
    out = app.handle_active_event(EVENT_A, None)
    assert out is None
    update_db_mock.assert_not_called()
    is_active_mock.assert_not_called()


@pytest.mark.parametrize('active', (True, False))
def test_handle_active_event(mocker, active):
    mocker.patch.object(
        app, 'scrape', autospec=True, return_value=b'some data'
    )
    update_db_mock = mocker.patch.object(app, 'update_db', autospec=True)
    mocker.patch.object(
        app, 'is_event_active', autospec=True, return_value=active
    )
    out = app.handle_active_event(deepcopy(EVENT_A), None)
    assert out is None
    if not active:
        update_db_mock.assert_called()
    else:
        update_db_mock.assert_not_called()


def test_build_notifiers():
    sub_db_mock = DynamoSubscribersDbMock('table')
    out = app.build_notifiers(sub_db_mock)
    subs_ids = []
    for notsub in out:
        subs = notsub.subscribers
        subs_ids.extend([sub.uri for sub in subs])
    subs_ids = sorted(subs_ids)
    assert subs_ids == ['uri1', 'uri2']


def test_run_job_no_db_active(mocker, job_mock):
    events_db_mock, update_db_mock, notify_mock, _ = job_mock
    events_db_mock.return_value = DynamoTrafficEventsDbMock([], 'table')

    app.run_job(None, None)

    assert update_db_mock.call_count == 2
    notify_mock.assert_called_with([], [EVENT_A, EVENT_B])


def test_run_job_one_db_active(job_mock):
    events_db_mock, update_db_mock, notify_mock, _ = job_mock
    events_db_mock.return_value = DynamoTrafficEventsDbMock([EVENT_A], 'table')

    app.run_job(None, None)

    assert update_db_mock.call_count == 1
    notify_mock.assert_called_with([], [EVENT_B])


def test_run_job_one_db_active(job_mock):
    events_db_mock, update_db_mock, notify_mock, _ = job_mock
    events_db_mock.return_value = DynamoTrafficEventsDbMock([EVENT_A], 'table')

    app.run_job(None, None)

    assert update_db_mock.call_count == 1
    notify_mock.assert_called_with([], [EVENT_B])


def test_run_job_one_db_active_to_handle(mocker, job_mock):
    events_db_mock, update_db_mock, notify_mock, _ = job_mock
    events_db_mock.return_value = DynamoTrafficEventsDbMock(
        [EVENT_A, EVENT_C], 'table'
    )
    handle_active_mock = mocker.patch.object(
        app, 'handle_active_event', autospec=True
    )

    app.run_job(None, None)

    assert update_db_mock.call_count == 1
    handle_active_mock.assert_called_once()
    notify_mock.assert_called_with([], [EVENT_B])


def test_run_job_no_event(mocker, job_mock):
    events_db_mock, _, notify_mock, fetch_events_mock = job_mock
    events_db_mock.return_value = DynamoTrafficEventsDbMock(
        [EVENT_A, EVENT_C], 'table'
    )
    fetch_events_mock.return_value = []
    handle_active_mock = mocker.patch.object(
        app, 'handle_active_event', autospec=True
    )

    app.run_job(None, None)

    assert handle_active_mock.call_count == 2
    notify_mock.assert_not_called()
