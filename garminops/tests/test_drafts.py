from copy import deepcopy

import pytest

from garminops.drafts import workout_copy, workout_update, zone_update
from garminops.policy import PolicyDenied, check_request, write_intent


def test_zone_update_preserves_unknown_fields_and_other_profiles():
    profiles = [{"sport": "DEFAULT", "maxHeartRateUsed": 180,
                 "lactateThresholdHeartRateUsed": None, "trainingMethod": "HR_MAX",
                 "vendorExtension": {"keep": True},
                 **{f"zone{i}Floor": 90 + i * 10 for i in range(1, 6)}},
                {"sport": "RUNNING", "maxHeartRateUsed": 190}]
    before = deepcopy(profiles)
    payload = zone_update(profiles, "DEFAULT", {"maxHeartRateUsed": 181})
    assert profiles == before
    assert len(payload) == 1
    assert payload[0]["maxHeartRateUsed"] == 181
    assert payload[0]["vendorExtension"] == {"keep": True}
    assert payload[0]["lactateThresholdHeartRateUsed"] is None
    assert payload[0]["changeState"] == "CHANGED"


def test_zone_fields_cannot_carry_historical_measurements():
    with pytest.raises(ValueError):
        zone_update([{"sport": "DEFAULT"}], "DEFAULT", {"activityId": 1})


def test_workout_copy_removes_record_identifiers_without_changing_source():
    original = {"workoutId": 1, "ownerId": 2, "workoutName": "Source",
                "sportType": {"sportTypeKey": "running"},
                "workoutSegments": [{"workoutSteps": [{"stepId": 3, "stepOrder": 1}]}]}
    copy = workout_copy(original, "Test", "Temporary")
    assert "workoutId" not in copy
    assert "stepId" not in copy["workoutSegments"][0]["workoutSteps"][0]
    assert original["workoutId"] == 1
    assert original["workoutSegments"][0]["workoutSteps"][0]["stepId"] == 3


def test_workout_update_keeps_full_document():
    original = {"workoutId": 1, "workoutName": "Before", "unknown": {"keep": True}}
    result = workout_update(original, {"workoutName": "After"})
    assert result["unknown"] == original["unknown"]
    with pytest.raises(ValueError):
        workout_update(original, {"ownerId": 9})


def test_permit_bound_to_exact_method_path_payload_and_scope():
    path = "/workout-service/workout/123"
    payload = {"workoutName": "Test"}
    with write_intent("PUT", path, payload):
        check_request("PUT", path, named_read=False, payload=payload)
        with pytest.raises(PolicyDenied):
            check_request("PUT", path, named_read=False, payload={"workoutName": "Other"})
        with pytest.raises(PolicyDenied):
            check_request("PUT", "/workout-service/workout/124", named_read=False, payload=payload)
        with pytest.raises(PolicyDenied):
            check_request("DELETE", "/activity-service/activity/123", named_read=False)
    with pytest.raises(PolicyDenied):
        check_request("PUT", path, named_read=False, payload=payload)


def test_permit_cannot_authorize_logged_data_or_device_writes():
    for method, path in [("DELETE", "/activity-service/activity/123"),
                         ("POST", "/device-service/devicemessage")]:
        with pytest.raises(PolicyDenied):
            with write_intent(method, path, {}):
                pytest.fail("Intent must not be granted")


def test_power_update_uses_single_object_and_preserves_other_data():
    from garminops.drafts import power_zone_update
    profiles=[{'sport':'CYCLING','functionalThresholdPower':200.0,'vendor':{'keep':True}},
              {'sport':'RUNNING','functionalThresholdPower':300.0}]
    before=deepcopy(profiles)
    payload=power_zone_update(profiles,'CYCLING',{'functionalThresholdPower':201})
    assert payload==before[0] | {'functionalThresholdPower':201}
    assert profiles==before


@pytest.mark.parametrize('changes', [
    {'activityId':7}, {'userLocalTime':'2026-10-02'}, {'functionalThresholdPower':True},
    {'functionalThresholdPower':float('nan')}, {'functionalThresholdPower':float('inf')},
    {'functionalThresholdPower':-1}, {'functionalThresholdPower':None}])
def test_power_rejects_non_configuration_and_invalid_numbers(changes):
    from garminops.drafts import power_zone_update
    with pytest.raises(ValueError):
        power_zone_update([{'sport':'CYCLING'}],'CYCLING',changes)
