import time
from copy import deepcopy

import pytest
from requests.exceptions import ReadTimeout

from dppnotifier.app import app
from dppnotifier.app.credentials import TelegramCredential
from dppnotifier.app.dpptypes import TrafficEvent
from dppnotifier.app.notifier import AlertTelegramNotifier
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
    out = app.handle_active_event(
        EVENT_A, mocker.Mock(), AlertTelegramNotifier()
    )
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
    out = app.handle_active_event(
        deepcopy(EVENT_A), mocker.Mock(), AlertTelegramNotifier()
    )
    assert out is None
    if not active:
        update_db_mock.assert_called()
    else:
        update_db_mock.assert_not_called()


def test_build_notifiers():
    sub_db_mock = DynamoSubscribersDbMock('table')
    out = app.build_notifiers(sub_db_mock, AlertTelegramNotifier())
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


def test_build_notifiers_alerting(mocker):
    sub_db = mocker.Mock()
    sub_db.get_subscribers = mocker.Mock(return_value=[])

    alert_notifier = AlertTelegramNotifier(
        alert_subscriber_uri=42,
        credential=TelegramCredential(token='token', name='name'),
    )
    alert_notifier.send_alert = mocker.Mock()
    app.build_notifiers(sub_db, alert_notifier)
    alert_notifier.send_alert.assert_called_with(
        alert='No notifier built - no notification will be send'
    )


@pytest.mark.parametrize(
    'exception_cls, exception_msg, raises',
    (
        (ReadTimeout, 'Request timeout', False),
        (IOError, 'Some other error', True),
    ),
)
def test_scrape_alerting_with_exceptions(
    mocker, exception_cls, exception_msg, raises
):
    mocker.patch.object(
        app,
        '_get_request',
        side_effect=exception_cls(exception_msg),
    )
    alert_notifier = AlertTelegramNotifier(
        alert_subscriber_uri=42,
        credential=TelegramCredential(token='token', name='name'),
    )
    alert_notifier.send_alert = mocker.Mock()
    if raises:
        with pytest.raises(exception_cls):
            app.scrape('dummy-url', alert_notifier)
            alert_notifier.send_alert.assert_called_with(alert=exception_msg)
    else:
        app.scrape('dummy-url', alert_notifier)
        alert_notifier.send_alert.assert_called_with(alert=exception_msg)


def test_get_request_retrying(mocker):
    mocker.patch(
        'dppnotifier.app.app.requests.get',
        side_effect=[ReadTimeout('Request timeout'), 'dummy_response'],
    )
    start_time = time.perf_counter()
    out = app._get_request('some-url')
    duration = time.perf_counter() - start_time
    dt = abs(duration - 5)
    assert dt < 0.2  # tolerance
    assert out == 'dummy_response'


def test_handle_active_event_alerting(mocker):
    mocker.patch.object(
        app, 'scrape', autospec=True, return_value=b'some data'
    )
    mocker.patch.object(
        app, 'update_db', autospec=True, side_effect=app.FailedUpsertEvent
    )
    mocker.patch.object(
        app, 'is_event_active', autospec=True, return_value=False
    )
    alert_notifier = AlertTelegramNotifier(
        alert_subscriber_uri=42,
        credential=TelegramCredential(token='token', name='name'),
    )

    alert_notifier.send_alert = mocker.Mock()

    app.handle_active_event(deepcopy(EVENT_A), mocker.Mock(), alert_notifier)

    msg = f'Failed to deactivate finished event {EVENT_A.event_id}'
    alert_notifier.send_alert.assert_called_with(alert=msg)
