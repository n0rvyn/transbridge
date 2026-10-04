from copy import deepcopy
from threading import RLock
from types import SimpleNamespace

import pytest

from garminops.goals import goal_payload, editable_goal
from garminops.policy import ContractUnverified, PolicyDenied, check_request, write_intent
from garminops.writes import execute, WriteFailure


def definition():
    return dict(name='Test', activityType='running', period='seven_days',
                type='count_accumulation', startDate='2099-10-10', privacy='public',
                numberOfActivities=2, distanceInMeters=None,
                durationInSeconds=None, caloriesInKiloCalories=None)


def zero_progress():
    return dict(percent=0, days=0, distanceInMeters=None, durationInSeconds=None,
                caloriesInKiloCalories=None, numberOfActivities=0)


class GoalAPI:
    display_name = 'test'
    full_name = 'Test'
    def __init__(self):
        self.client = self
        self.rows = {}
        self.calls = []
        self.ignore_delete = False
        self.fail_readback = False
    def get_goals(self, status):
        if self.fail_readback and self.calls:
            raise TimeoutError('read-back failure')
        return deepcopy(list(self.rows.values())) if status == 'future' else []
    def request(self, method, domain, path, **kwargs):
        self.calls.append((method, path, deepcopy(kwargs.get('json'))))
        data = kwargs.get('json')
        check_request(method, path, named_read=False, payload=data)
        if method == 'POST':
            self.rows[1] = data | dict(id=1, active=False, completed=False,
                                      progress=zero_progress())
        elif method == 'PUT':
            self.rows[1].update(data)
        elif not self.ignore_delete:
            del self.rows[1]
        result = deepcopy(self.rows.get(1))
        return SimpleNamespace(content=b'{}', json=lambda: result)


def backend():
    return SimpleNamespace(_api=GoalAPI(), _lock=RLock(), region='com', read=lambda *a: 'Test')


def test_goal_roundtrip_does_not_forward_progress_or_other_response_fields():
    b = backend()
    assert execute(b, 'create_goal', {'expected_account': 'test', 'goal': definition()})['verified']
    updated = execute(b, 'update_goal', {'expected_account': 'test', 'goal_id': 1, 'changes': {'name': 'Changed'}})
    assert updated['data']['name'] == 'Changed'
    assert 'progress' not in b._api.calls[-1][2]
    assert 'id' not in b._api.calls[-1][2]
    assert execute(b, 'delete_goal', {'expected_account': 'test', 'goal_id': 1})['data']['absent']


@pytest.mark.parametrize('changes', [{'startDate': '2020-01-01'}, {'progress': {'percent': 0}},
    {'numberOfActivities': True}, {'numberOfActivities': 2.5}, {'numberOfActivities': float('inf')},
    {'distanceInMeters': 100}, {'privacy': ''}])
def test_invalid_definitions_never_reach_transport(changes):
    b = backend()
    with pytest.raises((ValueError, ContractUnverified)):
        execute(b, 'create_goal', {'expected_account': 'test', 'goal': definition() | changes})
    assert not b._api.calls


@pytest.mark.parametrize('changes', [{'active': True}, {'completed': True}, {'progress': None},
    {'progress': {'numberOfActivities': 1}}, {'startDate': '2020-01-01'}])
def test_started_or_unclassified_goal_rejected_before_write(changes):
    b = backend()
    b._api.rows[1] = definition() | dict(id=1, active=False, completed=False, progress=zero_progress()) | changes
    with pytest.raises((ContractUnverified, ValueError)):
        execute(b, 'delete_goal', {'expected_account': 'test', 'goal_id': 1})
    assert not b._api.calls


def test_create_readback_failure_reports_created_id_without_retry():
    b = backend(); b._api.fail_readback = True
    with pytest.raises(WriteFailure) as exc:
        execute(b, 'create_goal', {'expected_account': 'test', 'goal': definition()})
    assert exc.value.outcome['completed_requests'][0]['response']['id'] == 1
    assert len(b._api.calls) == 1


def test_delete_success_without_absence_fails_verification():
    b = backend()
    execute(b, 'create_goal', {'expected_account': 'test', 'goal': definition()})
    b._api.ignore_delete = True
    with pytest.raises(WriteFailure):
        execute(b, 'delete_goal', {'expected_account': 'test', 'goal_id': 1})


def test_goal_intent_cannot_include_progress_or_use_dated_goal_route():
    with pytest.raises(ValueError):
        with write_intent('POST', '/goal-service/goal/goal', definition() | {'progress': {}}):
            pytest.fail('Progress passed boundary')
    with pytest.raises(PolicyDenied):
        with write_intent('PUT', '/goal-service/goal/user/effective/steps/2099-10-10', {'goalValue': 1}):
            pytest.fail('Dated-goal write passed boundary')


@pytest.mark.parametrize('operation', ['update_goal', 'delete_goal'])
@pytest.mark.parametrize('progress', [{}, {'percent': 0},
    zero_progress() | {'percent': None}, zero_progress() | {'days': False},
    zero_progress() | {'numberOfActivities': False},
    zero_progress() | {'distanceInMeters': 1},
    zero_progress() | {'percent': float('nan')}])
def test_incomplete_or_malformed_progress_blocks_every_existing_goal_write(operation, progress):
    b = backend()
    b._api.rows[1] = definition() | dict(id=1, active=False, completed=False, progress=progress)
    args = {'expected_account': 'test', 'goal_id': 1}
    if operation == 'update_goal':
        args['changes'] = {'name': 'Changed'}
    with pytest.raises(ContractUnverified):
        execute(b, operation, args)
    assert not b._api.calls
