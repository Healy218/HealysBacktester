from types import SimpleNamespace
from unittest.mock import Mock

from botocore.exceptions import ClientError
import pytest

from nn_meta.session_calendar import SessionCalendar
from scripts.retry_v6_context import availability, retry


def calendar():
    return SessionCalendar({'coverage_start': '2026-09-10', 'coverage_end': '2026-09-16',
                            'sessions': [{'date': day, 'open': '09:30', 'close': '16:00'}
                                         for day in ('2026-09-10', '2026-09-11',
                                                     '2026-09-14', '2026-09-15')]})


def test_current_pointer_makes_no_provider_request():
    client = Mock()
    result = availability(calendar(), {'through': '2026-09-14'}, '2026-09-15T15:00Z', client)
    assert result['status'] == 'current'
    client.head_object.assert_not_called()


def test_checks_intervening_sessions_and_keeps_missing_file_blocking():
    client = Mock()
    client.head_object.side_effect = [ClientError({'Error': {'Code': '404'}}, 'HeadObject'),
                                     {'ContentLength': 100}]
    result = availability(calendar(), {'through': '2026-09-10'}, '2026-09-15T15:00Z', client)
    assert result['status'] == 'waiting_for_provider'
    assert result['missing_keys'] == ['us_options_opra/minute_aggs_v1/2026/09/2026-09-11.csv.gz']
    assert client.head_object.call_count == 2
    command = Mock()
    retry(result, run=True, command=command)
    command.assert_not_called()


def test_permission_failure_is_not_misreported_as_publication_delay():
    client = Mock()
    client.head_object.side_effect = ClientError({'Error': {'Code': '403'}}, 'HeadObject')
    with pytest.raises(ClientError):
        availability(calendar(), {'through': '2026-09-11'}, '2026-09-15T15:00Z', client)


def test_calendar_boundary_and_naive_time_fail_closed():
    with pytest.raises(ValueError, match='does not cover'):
        availability(calendar(), {'through': '2026-09-14'}, '2026-09-17T15:00Z', Mock())
    with pytest.raises(ValueError, match='timezone'):
        availability(calendar(), {'through': '2026-09-14'}, '2026-09-15', Mock())


def test_available_data_only_requests_existing_refresh_when_services_idle():
    result = {'status': 'available'}
    command = Mock(return_value=SimpleNamespace(stdout='inactive\n'))
    assert retry(result, run=False, command=command) == result
    command.assert_not_called()
    assert retry(result, run=True, command=command)['status'] == 'refresh_requested'
    assert command.call_args.args[0] == ['systemctl', '--user', 'start', '--no-block', 'healys-v6-data.service']
    command.reset_mock()
    command.return_value.stdout = 'active\n'
    assert retry(result, run=True, command=command)['status'] == 'deferred_busy'
    assert command.call_count == 1
