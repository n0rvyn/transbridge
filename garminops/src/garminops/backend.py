from __future__ import annotations

import base64
import inspect
import json
import re
import threading
from uuid import UUID
from importlib.resources import files
from pathlib import Path
from datetime import date
from typing import Annotated, Any, Literal, get_type_hints

from garminconnect import Garmin, GarminConnectConnectionError, GarminConnectNotFoundError
from garminconnect.client import Client
from pydantic import AfterValidator, ConfigDict, Field, create_model

from .policy import PolicyDenied, check_request, clean_path
from .drafts import resource_id

SDK_READ_METHODS = tuple(json.loads(files(__package__).joinpath("read_methods.json").read_text()))
READ_METHODS = SDK_READ_METHODS + ("get_courses", "get_course", "get_effective_goals", "get_calendar_note", "get_calendar_event", "get_gear_items", "get_gear_item", "get_gear_usage_types", "get_gear_default_choices")


def calendar_day(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("Use YYYY-MM-DD.")
    return value


def gear_uuid(value: str) -> str:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError('Use a canonical Garmin gear UUID.')
    return value


class UpstreamResponseError(RuntimeError):
    pass


class ConnectorGarmin(Garmin):
    def get_gear_items(self, start: Annotated[int, Field(strict=True, ge=0)],
                       limit: Annotated[int, Field(strict=True, gt=0)],
                       status: Literal['ACTIVE', 'RETIRED']) -> list:
        """Read one explicit gear status with start and limit. Paginate ACTIVE and RETIRED separately to empty pages for a full inventory. Preserves usage and association fields without changing them."""
        if type(start) is not int or start < 0 or type(limit) is not int or limit <= 0:
            raise ValueError('Use a nonnegative start and positive page size.')
        if status not in ('ACTIVE', 'RETIRED'):
            raise ValueError('Use an explicit ACTIVE or RETIRED gear status.')
        data = self.connectapi('/gear-service/gear/v2/list', params={'start': start, 'limit': limit, 'gearStatuses': status})
        if not isinstance(data, list):
            raise UpstreamResponseError('Gear inventory did not return an array.')
        for row in data:
            if not isinstance(row, dict) or not isinstance(row.get('uuid'), str):
                raise UpstreamResponseError('Gear inventory contains a malformed identity.')
            try:
                gear_uuid(row['uuid'])
            except ValueError as exc:
                raise UpstreamResponseError('Gear inventory contains an invalid UUID.') from exc
        return data

    def get_gear_activities(self, gearUUID: Annotated[str, AfterValidator(gear_uuid)],
                            start: Annotated[int, Field(strict=True, ge=0)],
                            limit: Annotated[int, Field(strict=True, gt=0)]) -> list:
        """Read one explicit page of recorded activities linked to gear. Continue from start plus returned row count until empty. No silent limit clamp; preserves service errors and never changes associations."""
        gearUUID = gear_uuid(gearUUID)
        if type(start) is not int or start < 0 or type(limit) is not int or limit <= 0:
            raise ValueError('Use a nonnegative start and positive page size.')
        data = self.connectapi(f'/activitylist-service/activities/{gearUUID}/gear', params={'start':start,'limit':limit})
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise UpstreamResponseError('Gear activities did not return an array of records.')
        return data

    def get_gear_stats(self, gearUUID: Annotated[str, AfterValidator(gear_uuid)]) -> dict:
        """Read recorded gear usage statistics without treating a missing resource as zero usage. Preserves Garmin UUID formatting, totals and processing metadata."""
        gearUUID = gear_uuid(gearUUID)
        data = self.connectapi(f'/gear-service/gear/stats/{gearUUID}')
        if not isinstance(data, dict) or not isinstance(data.get('uuid'), str):
            raise UpstreamResponseError('Gear statistics have no resource identity.')
        try:
            matches = str(UUID(data['uuid'])) == gearUUID
        except ValueError:
            matches = False
        if not matches:
            raise UpstreamResponseError('Gear statistics identity differs from the requested gear.')
        return data

    def get_gear_default_choices(self, gear_type: Annotated[str, Field(pattern=r'^[A-Z][A-Z_]*$')]) -> list:
        """Read default activity-to-gear mappings for an explicit gear type such as SHOES or BIKE. Does not assign gear to past or future activities."""
        if not isinstance(gear_type, str) or not re.fullmatch(r'[A-Z][A-Z_]*', gear_type):
            raise ValueError('Use a gear type key such as SHOES or BIKE.')
        data = self.connectapi('/gear-service/gear/v2/default-gear-choices', params={'gearTypes': gear_type})
        if not isinstance(data, list):
            raise UpstreamResponseError('Default gear choices did not return an array.')
        for row in data:
            if (not isinstance(row, dict) or not isinstance(row.get('activityTypeKey'), str)
                    or not row['activityTypeKey'] or not isinstance(row.get('defaultGearUUIDs'), list)):
                raise UpstreamResponseError('Default gear choices contain unknown identity fields.')
            for uuid in row['defaultGearUUIDs']:
                try:
                    gear_uuid(uuid)
                except (TypeError, ValueError) as exc:
                    raise UpstreamResponseError('Default gear choices contain an invalid UUID.') from exc
        return data

    def get_gear_item(self, uuid: Annotated[str, AfterValidator(gear_uuid)]) -> dict:
        """Read one gear definition with recorded usage, association counts, images and collections. Does not change gear defaults or historical activity associations."""
        uuid = gear_uuid(uuid)
        data = self.connectapi(f'/gear-service/gear/v2/{uuid}')
        if (not isinstance(data, dict) or data.get('uuid') != uuid
                or any(not isinstance(data.get(k), str) for k in ('gearType', 'status', 'usageType'))):
            raise UpstreamResponseError('Gear details do not match the requested UUID or response shape.')
        return data

    def get_gear_usage_types(self) -> list:
        """Read Garmin's gear usage-tracking type catalog without choosing a default."""
        data = self.connectapi('/gear-service/gear/v2/usagetypes')
        if not isinstance(data, list) or any(not isinstance(v, str) for v in data):
            raise UpstreamResponseError('Gear usage types did not return a string array.')
        return data

    def get_calendar_event(self, event_id: Annotated[int, Field(strict=True, gt=0)]) -> dict:
        """Read one calendar event, including its activity and training-plan associations. Does not edit the event, subscribe, or change recorded results."""
        event_id = resource_id(event_id)
        data = self.connectapi(f"/calendar-service/event/{event_id}")
        if (not isinstance(data, dict) or type(data.get('id')) is not int
                or data['id'] != event_id
                or any(not isinstance(data.get(k), str) for k in ('eventName', 'date', 'eventType'))
                or not isinstance(data.get('eventPrivacy'), dict)
                or not isinstance(data.get('eventCustomization'), dict)):
            raise UpstreamResponseError('Calendar event does not match the requested resource or response shape.')
        return data

    def get_calendar_note(self, note_id: Annotated[int, Field(strict=True, gt=0)]) -> dict:
        """Read an independent calendar note by ID. Not an activity note or training-plan task."""
        note_id = resource_id(note_id)
        data = self.connectapi(f"/calendar-service/note/{note_id}")
        if (not isinstance(data, dict) or type(data.get('id')) is not int
                or data['id'] != note_id
                or any(not isinstance(data.get(k), str) for k in ('noteName', 'content', 'date'))):
            raise UpstreamResponseError('Calendar note does not match the requested resource.')
        return data

    def get_effective_goals(self, day: Annotated[str, AfterValidator(calendar_day)]) -> list:
        """Read daily goals effective on an explicit YYYY-MM-DD date. These differ from the independent active/future/past goals returned by get_goals. Does not change dated goals or recorded progress."""
        day = calendar_day(day)
        data = self.connectapi(f"/goal-service/goal/user/effective/{day}")
        if not isinstance(data, list) or any(
            not isinstance(row, dict) or not isinstance(row.get("goalType"), str)
            or type(row.get("goalValue")) not in (int, float)
            for row in data
        ):
            raise UpstreamResponseError("Effective goals did not return a goal array.")
        return data

    def get_userprofile_settings(self) -> dict:
        """Read current display preferences, including locale, time zone, date/time formats and units. Preserves upstream format objects and null values; changes no settings or logged data."""
        data = self.connectapi("/userprofile-service/userprofile/settings")
        if (not isinstance(data, dict)
                or not isinstance(data.get("measurementSystem"), str)
                or not isinstance(data.get("timeFormat"), dict)
                or not isinstance(data.get("dateFormat"), dict)):
            raise UpstreamResponseError("Display settings did not return the expected settings object.")
        return data

    def get_courses(self) -> list:
        """Read saved course listings. Empty lists are valid; route writes and device delivery are separate operations."""
        data = self.connectapi("/course-service/course")
        if not isinstance(data, list):
            raise UpstreamResponseError("Course listing did not return an array.")
        return data


    def get_course(self, course_id: Annotated[int, Field(strict=True, gt=0)]) -> dict:
        """Read one saved course with its geometry and waypoints. Does not edit the route or send it to a device. A deleted or absent course returns an upstream error."""
        course_id = resource_id(course_id)
        data = self.connectapi(f"/course-service/course/{course_id}")
        if not isinstance(data, dict) or type(data.get("courseId")) is not int or data["courseId"] != course_id:
            raise UpstreamResponseError("Course details do not match the requested resource.")
        return data


def error_metadata(error: Exception) -> dict:
    """Expose SDK exception class and its exact status prefix, never its body."""
    metadata = {"error": type(error).__name__}
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        response = getattr(current, "response", None)
        status = getattr(response, "status_code", None)
        if type(status) is int and 400 <= status < 600:
            metadata["http_status"] = status
            break
        if isinstance(current, (GarminConnectConnectionError, GarminConnectNotFoundError)):
            # Pinned Client emits this prefix; public SDK methods wrap it with
            # explicit causes. Never parse account-dependent response text.
            match = re.match(r"^API Error ([45][0-9]{2})(?:$| - )", str(current))
            if match:
                metadata["http_status"] = int(match.group(1))
                break
        current = current.__cause__
    return metadata


class LoginRequired(Exception):
    pass


class GuardedClient(Client):
    def _run_request(self, method: str, path: str, **kwargs: Any) -> Any:
        # This client is only owned by the curated reader adapter / local login.
        # Login and refresh use upstream's separate SSO machinery.
        check_request(method, path, named_read=True, payload=kwargs.get("json"))
        headers = kwargs.get("headers")
        if headers is not None:
            allowed = method.upper() == "GET" and (
                headers == {"Accept": "*/*"} or
                (clean_path(path) == "/goal-service/goal/goals" and
                 headers == {"Sec-Fetch-Site": "same-origin"}))
            if not allowed:
                raise PolicyDenied("Request contains unapproved headers.")
        forbidden = ("files", "data") + (("json",) if method.upper() == "GET" else ("params",))
        if any(k in kwargs for k in forbidden):
            raise PolicyDenied("Request contains an unexpected body, query or headers.")
        kwargs["allow_redirects"] = False
        response = super()._run_request(method, path, **kwargs)
        if 300 <= response.status_code < 400:
            raise PolicyDenied("API redirect rejected; credentials stay on the configured host.")
        return response


def make_api(region: str, **kwargs: Any) -> Garmin:
    if region not in ("com", "cn"):
        raise ValueError("Region must be com or cn.")
    api = ConnectorGarmin(is_cn=region == "cn", **kwargs)
    api.client = GuardedClient(domain=f"garmin.{region}")
    return api


def session_directory(region: str) -> Path:
    if region not in ("com", "cn"):
        raise ValueError("Region must be com or cn.")
    return Path.home() / ".config" / "transbridge" / "garmin" / region


def input_model(name: str):
    fn = getattr(ConnectorGarmin, name)
    hints = get_type_hints(fn, localns=vars(Garmin), include_extras=True)
    fields = {}
    for key, parameter in inspect.signature(fn).parameters.items():
        if key == "self":
            continue
        if parameter.kind in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL):
            raise RuntimeError(f"Unbounded arguments are not allowed: {name}")
        default = ... if parameter.default is inspect.Parameter.empty else parameter.default
        fields[key] = (hints.get(key, Any), default)
    return create_model(name + "Input", __config__=ConfigDict(extra="forbid"), **fields)


class Backend:
    def __init__(self, region: str = "com"):
        self.region = region
        self.session_dir = session_directory(region)
        self.models = {name: input_model(name) for name in READ_METHODS}
        self._api = None
        self._loaded_signature = None
        self._lock = threading.RLock()

    def status(self) -> dict:
        with self._lock:
            signature = self._session_signature()
            verified = (signature is not None and self._api is not None
                        and signature == self._loaded_signature)
        return {
            "stage": "development; not a finished connector",
            "region": f"garmin.{self.region}",
            "session_file_present": signature is not None,
            "session_verified_in_process": verified,
            "read_tools": len(READ_METHODS),
            "history_writes": "prohibited",
            "plans_and_settings": "named workout/calendar, future-goal, gear, heart-rate, power and display-unit tools registered; additional ordinary-account contracts remain under investigation",
            "device_actions": "separate authorization required; not registered",
            "chatgpt_remote_connection": "outside requested desktop-local scope",
            "delivery_target": "desktop local plugin with local Garmin login",
            "known_issues": [{"id": "KI-001", "issue": "FTHR null restoration unresolved; numeric zero is not unset",
                              "testing": "stopped by user; explicit reopening required", "release_blocker": False}],
            "deferred_todos": ["garmin.cn business validation", "Connect+-exclusive features"],
        }

    def _session_signature(self):
        token_path = self.session_dir / "garmin_tokens.json"
        try:
            stat = token_path.stat()
        except FileNotFoundError:
            return None
        return (stat.st_mtime_ns, stat.st_size) if token_path.is_file() else None

    def read(self, name: str, arguments: dict) -> Any:
        if name not in self.models:
            raise PolicyDenied("Not a registered read operation.")
        values = self.models[name].model_validate(arguments)
        params = {field: getattr(values, field) for field in type(values).model_fields}
        with self._lock:
            token_path = self.session_dir / "garmin_tokens.json"
            signature = self._session_signature()
            if signature != self._loaded_signature:
                self._api = None
            if self._api is None:
                if not (self.session_dir / "garmin_tokens.json").is_file():
                    raise LoginRequired(f"Run garminops login --region {self.region} locally.")
                api = make_api(self.region)
                try:
                    api.login(str(self.session_dir))
                except Exception as exc:
                    exc.garminops_stage = "session_resume"
                    raise
                self._api = api
                stat = token_path.stat()
                self._loaded_signature = (stat.st_mtime_ns, stat.st_size)
            try:
                if name == "get_unit_system":
                    # Read current settings rather than the login-time cache.
                    result = self._api.get_user_profile().get("userData", {}).get("measurementSystem")
                else:
                    result = getattr(self._api, name)(**params)
            except Exception as exc:
                exc.garminops_stage = "upstream_read"
                raise
        # Preserve upstream data without guessing its field structure.
        if isinstance(result, bytes):
            return {"encoding": "base64", "data": base64.b64encode(result).decode("ascii")}
        return result
