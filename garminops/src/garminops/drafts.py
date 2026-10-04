"""Payload builders based on inspected live read samples; no network effects."""

from copy import deepcopy
from datetime import date


def resource_id(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("Resource ID must be a positive integer.")
    return value


def workout_copy(source: dict, name: str, description: str) -> dict:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Workout name cannot be empty.")
    if not isinstance(description, str):
        raise ValueError("Description must be text.")
    if not isinstance(source.get("workoutSegments"), list) or not isinstance(source.get("sportType"), dict):
        raise ValueError("Expected a complete workout template, not a list summary.")
    draft = deepcopy(source)
    for key in ("workoutId", "ownerId", "createdDate", "updatedDate", "updateDate", "author",
                "sharedWithUsers", "trainingPlanId", "atpPlanId", "consumer", "consumerName",
                "consumerImageURL", "consumerWebsiteURL", "workoutProvider", "workoutSourceId",
                "uploadTimestamp"):
        draft.pop(key, None)
    def strip_ids(value):
        if isinstance(value, dict):
            for key in ("stepId", "childStepId", "workoutId", "ownerId"):
                value.pop(key, None)
            for child in value.values():
                strip_ids(child)
        elif isinstance(value, list):
            for child in value:
                strip_ids(child)
    strip_ids(draft)
    draft.update(workoutName=name, description=description, shared=False)
    return draft


def workout_update(source: dict, changes: dict) -> dict:
    allowed = {"workoutName", "description", "workoutSegments", "sportType", "subSportType",
               "poolLength", "poolLengthUnit", "estimatedDurationInSecs", "estimatedDistanceInMeters",
               "estimatedDistanceUnit", "estimateType", "avgTrainingSpeed", "isSessionTransitionEnabled"}
    if not changes or set(changes) - allowed:
        raise ValueError("Only training-template fields can be changed.")
    resource_id(source.get("workoutId"))
    if "workoutName" in changes and (not isinstance(changes["workoutName"], str) or not changes["workoutName"].strip()):
        raise ValueError("Workout name cannot be empty.")
    return deepcopy(source) | deepcopy(changes)


def schedule_payload(day: str) -> dict:
    parsed = date.fromisoformat(day)
    if parsed.isoformat() != day:
        raise ValueError("Use YYYY-MM-DD.")
    return {"date": day}


ZONE_FIELDS = {"maxHeartRateUsed", "restingHeartRateUsed", "lactateThresholdHeartRateUsed",
               "restingHrAutoUpdateUsed", "trainingMethod", *(f"zone{i}Floor" for i in range(1, 6))}


def zone_update(profiles: list[dict], sport: str, changes: dict) -> list[dict]:
    if not changes or set(changes) - ZONE_FIELDS:
        raise ValueError("Only explicit heart-rate configuration fields can be changed.")
    matching = [p for p in profiles if p.get("sport") == sport]
    if len(matching) != 1:
        raise ValueError("Expected one existing profile for the exact sport; no implicit fallback.")
    for key, value in changes.items():
        if key == "trainingMethod":
            if value not in ("HR_MAX", "HR_RESERVE", "LACTATE_THRESHOLD"):
                raise ValueError("Unknown Garmin calculation method.")
        elif key == "restingHrAutoUpdateUsed":
            if not isinstance(value, bool):
                raise ValueError("Automatic resting HR selection must be explicit true/false.")
        elif value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
            raise ValueError("Heart-rate fields use positive integer BPM or null.")
    merged = deepcopy(matching[0]) | deepcopy(changes)
    floors = [merged.get(f"zone{i}Floor") for i in range(1, 6)]
    if all(isinstance(x, int) and not isinstance(x, bool) for x in floors):
        if any(a >= b for a, b in zip(floors, floors[1:])):
            raise ValueError("Zone floors must increase strictly.")
    merged["changeState"] = "CHANGED"
    return [merged]


POWER_FIELDS = {"functionalThresholdPower", *(f"zone{i}Floor" for i in range(1, 8))}


def power_zone_update(profiles: list[dict], sport: str, changes: dict) -> dict:
    """Power settings use a single object, unlike heart-rate profile arrays."""
    from math import isfinite
    if not changes or set(changes) - POWER_FIELDS:
        raise ValueError("Only explicit power configuration fields can be changed.")
    matching = [profile for profile in profiles if profile.get('sport') == sport]
    if len(matching) != 1:
        raise ValueError("Expected one existing power profile for the exact sport.")
    for value in changes.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ValueError("Power settings require finite non-negative watts; zero is a literal value, not null.")
    merged = deepcopy(matching[0]) | deepcopy(changes)
    if any(key.startswith('zone') for key in changes):
        floors = [merged.get(f'zone{i}Floor') for i in range(1, 8)]
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x) for x in floors):
            raise ValueError("Expected seven numeric power-zone floors.")
        if any(floors) and any(a >= b for a, b in zip(floors, floors[1:])):
            raise ValueError("Power-zone floors must increase strictly.")
    return merged


def calendar_note_payload(value: dict) -> dict:
    """Only an independent future planning note, never an activity annotation."""
    from .policy import ContractUnverified
    if not isinstance(value, dict) or set(value) != {'id', 'noteName', 'content', 'date'}:
        raise ValueError('Only independent note definition fields are accepted.')
    if value['id'] is not None:
        resource_id(value['id'])
    if not isinstance(value['noteName'], str) or not value['noteName'].strip():
        raise ValueError('Note name must be nonempty text.')
    if not isinstance(value['content'], str):
        raise ValueError('Note content must be text.')
    schedule_payload(value['date'])
    if date.fromisoformat(value['date']) <= date.today():
        raise ContractUnverified('Only future planning-note write contracts are verified.')
    return deepcopy(value)
