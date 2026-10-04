import json
import pytest
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from garminops.backend import error_metadata


@pytest.mark.parametrize('exception,status', [(GarminConnectConnectionError,429),(GarminConnectNotFoundError,404)])
def test_known_status_survives_without_private_response(exception, status):
    result = error_metadata(exception(f'API Error {status} - secret-token private-email raw-response'))
    assert result == {'error':exception.__name__, 'http_status':status}
    assert 'secret' not in json.dumps(result)


@pytest.mark.parametrize('error', [
    RuntimeError('API Error 429 - arbitrary exception'),
    GarminConnectConnectionError('Unexpected body 429 secret'),
    GarminConnectConnectionError('API Error 4299 - malformed'),
    GarminConnectConnectionError('API Error 200 - unexpected'),
])
def test_does_not_guess_status_from_unrecognized_errors(error):
    assert error_metadata(error) == {'error':type(error).__name__}


def test_preserves_status_through_sdk_exception_wrapping():
    original = GarminConnectNotFoundError('API Error 404 - private-body')
    wrapper = GarminConnectNotFoundError('Download failed; private-body')
    wrapper.__cause__ = original
    assert error_metadata(wrapper) == {'error':'GarminConnectNotFoundError', 'http_status':404}


def test_cyclic_causes_terminate_without_exposing_messages():
    error = RuntimeError('private')
    error.__cause__ = error
    assert error_metadata(error) == {'error':'RuntimeError'}
