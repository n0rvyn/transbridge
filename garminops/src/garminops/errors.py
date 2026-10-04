"""Stable diagnostics. Exception messages, URLs and payloads are never exported."""
import logging
from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError
from curl_cffi.requests.exceptions import Timeout as CurlTimeout, ConnectionError as CurlConnectionError
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError


def suppress_private_logs():
    # SDK debug/error messages can contain entire responses and login URLs.
    logging.getLogger('garminconnect').disabled = True
    logging.getLogger('garminconnect.client').disabled = True


def diagnostics(error, *, stage, operation=None, status=None):
    chain, seen = [], set()
    current = error
    code, cause, action, retriable = 'unknown_failure', 'unknown', 'Inspect the stage and exception types; the cause is unknown.', None
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        # Only identifiers from code, never dynamically supplied exception text.
        name = type(current).__name__
        chain.append({'type': name if name.isidentifier() else 'Exception'})
        if isinstance(current, GarminConnectAuthenticationError):
            code, cause, action, retriable = 'authentication_failed', 'SDK authentication rejected', 'Complete local login in your own terminal.', False
        elif isinstance(current, GarminConnectTooManyRequestsError):
            code, cause, action, retriable = 'rate_limited', 'Upstream rate limit', 'Wait before retrying; respect upstream retry guidance.', True
        elif isinstance(current, (Timeout, CurlTimeout, TimeoutError)):
            code, cause, action, retriable = 'transport_timeout', 'Transport timed out', 'Check connectivity and retry reads after a delay.', True
        elif isinstance(current, (RequestsConnectionError, CurlConnectionError)):
            code, cause, action, retriable = 'transport_connection_failed', 'Transport connection failed', 'Check connectivity and upstream availability.', True
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    if status is not None:
        if status == 429:
            code, cause, action, retriable = 'rate_limited', 'HTTP 429', 'Wait before retrying; respect upstream retry guidance.', True
        elif status == 401:
            code, cause, action, retriable = 'authentication_failed', 'HTTP 401', 'Complete local login in your own terminal.', False
        elif status == 403:
            code, cause, action, retriable = 'upstream_forbidden', 'HTTP 403; reason unknown', 'Inspect upstream access requirements; do not assume an account or permission cause.', False
        elif status == 404:
            code, cause, action, retriable = 'resource_not_found', 'HTTP 404', 'Check the resource identifier and whether it still exists.', False
        elif status >= 500:
            code, cause, action, retriable = 'upstream_unavailable', f'HTTP {status}', 'Retry reads after a delay.', True
        else:
            code, cause, action, retriable = 'upstream_request_rejected', f'HTTP {status}; reason unknown', 'Check the documented operation contract.', False
    if type(error).__name__ == 'UpstreamResponseError':
        code, cause, action, retriable = 'upstream_response_invalid', 'Response failed the connector contract', 'Report the operation and stage for contract investigation.', None
    value = dict(code=code, stage=stage, cause=cause, action=action, retriable=retriable, error_chain=chain)
    if operation is not None:
        value['operation'] = operation
    return value


def local_diagnostics(code):
    return dict(code=code, stage='validation', cause=code, retriable=False,
                action='Check the described operation schema and connector contract.', error_chain=[])


# Audited static connector messages; unknown/dynamic messages remain suppressed.
SAFE_CONTRACT_DETAILS = frozenset({
    'Active gear unexpectedly retains a retirement date.',
    'Another gear item already owns a requested default; replacement effects remain unverified.',
    'Changes to started goals can affect historical progress; only future goal contracts are verified.',
    'Course and image attachment contracts are not verified.',
    'Default gear mappings contain duplicate identities.',
    'Event has recorded results, plan associations, customizations or incomplete state.',
    'Event response contains missing or unverified fields.',
    'Garmin ignores null; clearing settings is unresolved. No write sent.',
    'Gear detail has missing or unverified state.',
    'Gear has recorded usage or an unknown association count.',
    'Goal has recorded or unclassified progress; no write sent.',
    'Goal progress is incomplete or unclassified.',
    'Only active, fully processed, independent gear has a verified write contract.',
    'Only defaultGear true and preferredGear false have a verified contract.',
    'Only future planning-note write contracts are verified.',
    'Only independent events owned by this account have a verified write contract.',
    'Only the complete gear definition is supported; no usage records or associations.',
    'Only the explicit event definition fields are supported; never send results or associations.',
    'Past or current-day event changes require a separately verified history-preserving contract.',
    'Protected schedule contract is unverified.',
    'Public, shared and official event contracts are not verified.',
    'Retired gear has an unknown retirement date.',
    'Shared or discoverable event writes are not verified.',
    'Started, completed or unclassified goal cannot be changed.',
    'This gear type has no verified definition contract.',
    'Use the named default-setting operation for default activity assignments.',
    'Write contract not registered; no request was sent.',
})

def contract_detail(error):
    text = str(error)
    return text if text in SAFE_CONTRACT_DETAILS else "The operation contract requires further verification."
