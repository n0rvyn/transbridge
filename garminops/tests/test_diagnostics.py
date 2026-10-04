import json
import logging
import pytest
from requests.exceptions import Timeout, ConnectionError
from curl_cffi.requests.exceptions import Timeout as CurlTimeout
from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError
from garminops.errors import diagnostics, suppress_private_logs
from garminops.server import result


@pytest.mark.parametrize('error,code,retry', [
    (Timeout('secret'), 'transport_timeout', True),
    (CurlTimeout('secret'), 'transport_timeout', True),
    (ConnectionError('secret'), 'transport_connection_failed', True),
    (GarminConnectAuthenticationError('secret'), 'authentication_failed', False),
    (GarminConnectTooManyRequestsError('secret'), 'rate_limited', True),
    (RuntimeError('unauthorized password secret'), 'unknown_failure', None),
])
def test_typed_evidence(error, code, retry):
    value = diagnostics(error, stage='upstream_read', operation='get_steps')
    assert value['code'] == code
    assert value['retriable'] is retry
    assert value['stage'] == 'upstream_read'
    assert 'secret' not in json.dumps(value)


@pytest.mark.parametrize('status,code', [(401,'authentication_failed'), (403,'upstream_forbidden'), (404,'resource_not_found'), (429,'rate_limited'), (503,'upstream_unavailable'), (400,'upstream_request_rejected')])
def test_http_evidence(status, code):
    assert diagnostics(RuntimeError(), stage='request', status=status)['code'] == code


def test_private_chain_and_cycle_are_suppressed():
    private = 'password=pw Bearer token https://user:pass@example.com/?ticket=ST-secret {"heartRate":177,"sleep":"private"} email@example.com'
    outer = RuntimeError(private)
    inner = Timeout(private)
    outer.__cause__ = inner
    inner.__cause__ = outer
    value = diagnostics(outer, stage='request')
    assert value['error_chain'] == [{'type':'RuntimeError'}, {'type':'Timeout'}]
    assert private not in json.dumps(value)
    assert all(word not in json.dumps(value) for word in ['ST-secret','heartRate','email@example.com','user:pass'])


def test_mcp_legacy_shape_preserved():
    value = result({'error':'invalid_arguments','request_sent':False}, True)
    assert value.isError is True
    assert json.loads(value.content[0].text) == value.structuredContent
    assert value.structuredContent['error'] == 'invalid_arguments'
    assert value.structuredContent['code'] == 'invalid_arguments'


def test_sdk_logs_never_emit_private_payload(caplog):
    suppress_private_logs()
    with caplog.at_level(logging.DEBUG):
        logging.getLogger('garminconnect.client').error('password=secret heartRate=177')
    assert not caplog.records


def test_partial_write_timeout_requires_state_check():
    from test_writes import backend, ACCOUNT
    from garminops.writes import execute, WriteFailure
    with pytest.raises(WriteFailure) as caught:
        execute(backend(), 'reschedule_workout', {'expected_account':ACCOUNT,'schedule_id':11,'day':'2026-10-04'})
    out = caught.value.outcome
    assert out['code'] == 'transport_timeout'
    assert out['stage'] == 'request'
    assert out['operation'] == 'reschedule_workout'
    assert out['retriable'] is False
    assert out['retry_requires_state_check'] is True
    assert out['completed_requests'][0]['response']['workoutScheduleId'] == 12


def test_known_contract_detail_preserved_unknown_private_detail_suppressed():
    from garminops.errors import contract_detail
    from garminops.policy import ContractUnverified
    known = 'Gear has recorded usage or an unknown association count.'
    assert contract_detail(ContractUnverified(known)) == known
    assert 'secret' not in contract_detail(ContractUnverified('secret health payload'))


def test_import_does_not_disable_sdk_logs():
    import subprocess
    from pathlib import Path
    import sys
    source = str(Path(__file__).resolve().parents[1] / 'src')
    script = "import sys, logging; sys.path.insert(0, sys.argv[1]); import garminops.backend; assert not logging.getLogger('garminconnect').disabled; assert not logging.getLogger('garminconnect.client').disabled"
    subprocess.run([sys.executable, '-c', script, source], check=True)


def test_suppressed_sdk_logs_leave_typed_error_action_available(caplog):
    suppress_private_logs()
    error = GarminConnectAuthenticationError('password=secret')
    logging.getLogger('garminconnect.client').error(str(error))
    value = diagnostics(error, stage='session_resume')
    assert value['code'] == 'authentication_failed'
    assert value['action'] == 'Complete local login in your own terminal.'
    assert not caplog.records
