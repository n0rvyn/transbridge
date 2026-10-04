"""Category policy and outbound data-request checks, independent of MCP hints."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import re
from urllib.parse import unquote, urlsplit


class PolicyDenied(Exception):
    pass


class ContractUnverified(PolicyDenied):
    pass


@dataclass(frozen=True)
class WriteIntent:
    method: str
    path: str
    payload_hash: str


_intent: ContextVar[WriteIntent | None] = ContextVar("garmin_write_intent", default=None)


def payload_hash(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def known_write_route(method: str, path: str) -> bool:
    return bool(
        (method == "POST" and path == "/workout-service/workout")
        or (method == "POST" and path == "/calendar-service/note")
        or (method == "POST" and path == "/calendar-service/event")
        or (method == "POST" and path == "/gear-service/gear/v2")
        or (method == "PUT" and re.fullmatch(r"/gear-service/gear/v2/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/status/(ACTIVE|RETIRED)", path))
        or (method in ("PUT", "DELETE") and re.fullmatch(r"/gear-service/gear/v2/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", path))
        or (method in ("PUT", "DELETE") and re.fullmatch(r"/calendar-service/event/[1-9][0-9]*", path))
        or (method in ("PUT", "DELETE") and re.fullmatch(r"/calendar-service/note/[1-9][0-9]*", path))
        or (method == "POST" and path == "/goal-service/goal/goal")
        or (method in ("PUT", "DELETE") and re.fullmatch(r"/goal-service/goal/goal/[1-9][0-9]*", path))
        or (method in ("PUT", "DELETE") and re.fullmatch(r"/workout-service/workout/[1-9][0-9]*", path))
        or (method in ("POST", "DELETE") and re.fullmatch(r"/workout-service/schedule/[1-9][0-9]*", path))
        or (method == "PUT" and path in ("/biometric-service/heartRateZones", "/biometric-service/powerZones", "/userprofile-service/userprofile/user-settings"))
    )


def check_write_payload(path: str, payload) -> None:
    if path == '/gear-service/gear/v2' or path.startswith('/gear-service/gear/v2/'):
        if payload is not None:
            from .gear import gear_payload
            gear_payload(payload, allow_defaults=True)
            expected = None if path == '/gear-service/gear/v2' else path.rsplit('/', 1)[1]
            if payload['uuid'] != expected:
                raise PolicyDenied('Gear payload UUID differs from its route.')
    if path == '/calendar-service/event' or path.startswith('/calendar-service/event/'):
        if payload is not None:
            from .events import event_payload
            event_payload(payload)
            expected = None if path == '/calendar-service/event' else int(path.rsplit('/', 1)[1])
            if payload.get('id') != expected:
                raise PolicyDenied('Calendar event payload ID differs from its route.')
    if path == '/goal-service/goal/goal' or path.startswith('/goal-service/goal/goal/'):
        if payload is not None:
            from .goals import goal_payload
            goal_payload(payload)
    if path == '/calendar-service/note' or path.startswith('/calendar-service/note/'):
        if payload is not None:
            from .drafts import calendar_note_payload
            calendar_note_payload(payload)
            expected = None if path == '/calendar-service/note' else int(path.rsplit('/', 1)[1])
            if payload['id'] != expected:
                raise PolicyDenied('Calendar note payload ID differs from its route.')
    # This endpoint mixes preferences and logged-value setters. Never permit a
    # full profile object, even inside a scoped write intent.
    if path == "/userprofile-service/userprofile/user-settings":
        if (not isinstance(payload, dict) or set(payload) != {"userData"}
                or not isinstance(payload["userData"], dict)
                or set(payload["userData"]) != {"measurementSystem"}
                or not isinstance(payload["userData"]["measurementSystem"], str)
                or not payload["userData"]["measurementSystem"]):
            raise PolicyDenied("Only the explicit measurement-system preference can be written here.")


@contextmanager
def write_intent(method: str, path: str, payload=None):
    """Internal scoped permit. Never accepted from MCP tool arguments."""
    path = clean_path(path)
    method = method.upper()
    if not known_write_route(method, path):
        raise PolicyDenied("This write route is not registered.")
    check_write_payload(path, payload)
    token = _intent.set(WriteIntent(method, path, payload_hash(payload)))
    try:
        yield
    finally:
        _intent.reset(token)


def clean_path(path: str) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        raise PolicyDenied("Only absolute API paths are accepted.")
    decoded = path
    # Reject encoded metacharacters even when encoded more than once.
    while True:
        result = unquote(decoded)
        if result == decoded:
            break
        decoded = result
    parsed = urlsplit(decoded)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or "\\" in decoded or "//" in decoded
            or any(ord(c) < 32 for c in decoded)
            or any(s.split(";", 1)[0] in (".", "..") for s in decoded.split("/"))):
        raise PolicyDenied("Non-canonical API path rejected.")
    return decoded


def check_request(method: str, path: str, *, named_read: bool, payload=None) -> None:
    """No unverified write can reach Garmin through this development adapter.

    Product writes must match a registered route and the exact request produced
    by a named operation. A generic HTTP request has no scoped intent.
    """
    path = clean_path(path)
    if method.upper() == "GET" and named_read:
        return
    method = method.upper()
    expected = _intent.get()
    if known_write_route(method, path) and expected == WriteIntent(method, path, payload_hash(payload)):
        check_write_payload(path, payload)
        return
    if path.startswith(("/activity-service/", "/upload-service/",
                        "/weight-service/", "/bloodpressure-service/",
                        "/wellness-service/", "/periodichealth-service/")):
        raise PolicyDenied("Logged data is immutable; request blocked before dispatch.")
    if path.startswith("/device-service/devicemessage"):
        raise PolicyDenied("Device action requires separate authorization.")
    raise ContractUnverified("Write contract not registered; no request was sent.")
