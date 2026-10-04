"""Offline checks for recovery of IDs from partial live test outcomes."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('live_verifier',
    Path(__file__).resolve().parents[2]/'scripts/verify_garmin_live.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_resource_ids_survive_failed_readback_and_reschedule():
    outcome = {'verified': False, 'completed_requests': [
        {'response': {'workoutScheduleId': 42}}, {'response': None}]}
    assert module.returned_ids(outcome, 'workoutScheduleId') == {42}
    assert module.returned_ids(outcome, 'workoutId') == set()


def test_only_explicit_returned_resource_ids_are_cleanup_candidates():
    outcome = {'data': {'workoutId': 7}, 'last_request': {'path': '/workout/99'},
               'completed_requests': [{'response': {'workoutId': 7}},
                                      {'response': {'ownerId': 10}}]}
    assert module.returned_ids(outcome, 'workoutId') == {7}


def test_gear_uuid_survives_failed_readback_without_path_inference():
    uuid = '00000000-0000-4000-8000-000000000001'
    outcome = {'completed_requests': [{'response': {'uuid': uuid}},
        {'response': {'uuid': '../activity/1'}}, {'response': {'uuid': 123}}],
        'last_request': {'path': '/gear-service/gear/v2/another-id'}}
    assert module.returned_ids(outcome, 'uuid') == {uuid}


def test_invalid_numeric_cleanup_ids_are_rejected():
    outcome = {'completed_requests': [{'response': {'id': v}} for v in (True, 0, -1, '12')]}
    assert module.returned_ids(outcome, 'id') == set()
