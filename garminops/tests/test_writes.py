from types import SimpleNamespace
from threading import RLock

import pytest

from garminops.policy import PolicyDenied, ContractUnverified
from garminops.writes import execute, PlanWriter, WriteFailure

ACCOUNT = 'test-account-id'

class Response:
    content = b'{}'
    def __init__(self, data): self.data = data
    def json(self): return self.data

class FakeAPI:
    display_name = ACCOUNT
    full_name = 'Test'
    def __init__(self):
        self.client = self
        self.calls = []
        self.original = {'workoutScheduleId': 11, 'calendarDate':'2026-10-03',
            'workout': {'workoutId':7}, 'associatedActivityId':None,
            'associatedActivityDateTime':None, 'protected':False}
    def get_scheduled_workout_by_id(self, sid):
        return self.original if sid == 11 else self.original | {'workoutScheduleId':12, 'calendarDate':'2026-10-04'}
    def get_workout_by_id(self, wid): return {'workoutId':wid}
    def get_scheduled_workouts(self, year, month):
        return {'calendarItems':[{'id':12,'workoutId':7,'date':'2026-10-04'}]}
    def request(self, method, domain, path, **kwargs):
        self.calls.append((method,path))
        if method == 'DELETE': raise TimeoutError('test failure')
        return Response({'workoutScheduleId':12})


def backend():
    api = FakeAPI()
    return SimpleNamespace(_api=api, _lock=RLock(), region='com', read=lambda *args: 'Test')


def test_account_mismatch_never_reaches_resources_or_transport():
    b = backend()
    b._api.get_workout_by_id = lambda _: pytest.fail('Resource accessed for wrong account')
    with pytest.raises(PolicyDenied):
        execute(b, 'delete_workout', {'expected_account':'other', 'workout_id':7})
    assert b._api.calls == []


@pytest.mark.parametrize('field,value', [('associatedActivityId',999),
    ('associatedActivityDateTime','2026-10-03T12:00:00'), ('protected',True)])
def test_completed_or_protected_schedule_cannot_be_changed(field, value):
    b = backend()
    b._api.original[field] = value
    with pytest.raises(PolicyDenied):
        execute(b, 'unschedule_workout', {'expected_account':ACCOUNT, 'schedule_id':11})
    assert b._api.calls == []


def test_absent_activity_association_is_not_treated_as_uncompleted():
    b = backend()
    del b._api.original['associatedActivityId']
    with pytest.raises(PolicyDenied):
        execute(b, 'unschedule_workout', {'expected_account':ACCOUNT, 'schedule_id':11})
    assert b._api.calls == []


def test_reschedule_failure_reports_created_replacement_without_retrying():
    b = backend()
    with pytest.raises(WriteFailure) as err:
        execute(b, 'reschedule_workout', {'expected_account':ACCOUNT,'schedule_id':11,'day':'2026-10-04'})
    out = err.value.outcome
    assert out['verified'] is False
    assert out['completed_requests'][0]['response']['workoutScheduleId'] == 12
    assert out['last_request'] == {'method':'DELETE','path':'/workout-service/schedule/11'}
    assert b._api.calls == [('POST','/workout-service/schedule/7'),('DELETE','/workout-service/schedule/11')]


@pytest.mark.skip(reason='KI-001: user stopped null-clearing/restoration tests; reopen only on explicit request.')
def test_null_clear_reports_unresolved_contract_without_network_write():
    b = backend()
    with pytest.raises(ContractUnverified):
        execute(b, 'update_heart_rate_zones', {'expected_account':ACCOUNT,'sport':'DEFAULT',
            'changes':{'lactateThresholdHeartRateUsed':None}})
    assert b._api.calls == []


def test_delete_uses_exact_resource_absence_not_paginated_list():
    from garminconnect import GarminConnectNotFoundError
    b = backend()
    deleted = False
    def detail(wid):
        if deleted: raise GarminConnectNotFoundError('404')
        return {'workoutId':wid}
    def request(*args, **kwargs):
        nonlocal deleted
        deleted = True
        return Response(None)
    b._api.get_workout_by_id = detail
    b._api.request = request
    b._api.get_workouts = lambda **kwargs: pytest.fail('A list is not exact resource absence')
    out = execute(b, 'delete_workout', {'expected_account':ACCOUNT,'workout_id':7})
    assert out['verified'] and out['data']['absent']


def test_successful_delete_response_without_actual_deletion_is_not_success():
    b = backend()
    b._api.request = lambda *args, **kwargs: Response(None)
    with pytest.raises(WriteFailure) as exc:
        execute(b, 'delete_workout', {'expected_account':ACCOUNT,'workout_id':7})
    assert not exc.value.outcome['verified']


def test_create_does_not_report_success_when_server_drops_workout_steps():
    b = backend()
    b._api.request = lambda *a, **k: Response({'workoutId':7})
    b._api.get_workout_by_id = lambda _: {'workoutId':7,'workoutName':'Test',
        'description':'Temporary','sportType':{'sportTypeKey':'running'},'workoutSegments':[]}
    with pytest.raises(WriteFailure):
        execute(b,'create_workout',{'expected_account':ACCOUNT,'name':'Test','description':'Temporary',
            'workout':{'sportType':{'sportTypeKey':'running'},'workoutSegments':[
                {'workoutSteps':[{'stepOrder':1,'endConditionValue':300}]}]}})


def test_update_steps_accepts_generated_fields_without_losing_requested_content():
    b = backend()
    requested=[{'workoutSteps':[{'stepOrder':1,'endConditionValue':300}]}]
    confirmed={'workoutId':7,'workoutSegments':[{'segmentOrder':1,'workoutSteps':[
        {'stepId':99,'stepOrder':1,'endConditionValue':300}]}]}
    b._api.get_workout_by_id=lambda _: confirmed
    b._api.request=lambda *a,**k: Response(confirmed)
    out=execute(b,'update_workout',{'expected_account':ACCOUNT,'workout_id':7,
        'changes':{'workoutSegments':requested}})
    assert out['verified']


def test_step_update_allows_regenerated_ids_but_rejects_changed_content():
    from garminops.writes import contains_requested_content
    expected={'workoutSteps':[{'stepId':1,'stepOrder':1,'endConditionValue':300}]}
    assert contains_requested_content({'workoutSteps':[
        {'stepId':2,'stepOrder':1,'endConditionValue':300}]}, expected)
    assert not contains_requested_content({'workoutSteps':[
        {'stepId':2,'stepOrder':1,'endConditionValue':600}]}, expected)
    assert not contains_requested_content({'workoutSteps':[]}, expected)
    assert not contains_requested_content({'workoutSteps':[
        {'stepId':2,'stepOrder':2,'endConditionValue':300}]}, expected)


def test_power_update_checks_other_profiles_and_reports_partial_outcome():
    b=backend()
    before=[{'sport':'CYCLING','functionalThresholdPower':200},
            {'sport':'RUNNING','functionalThresholdPower':250}]
    after=[{'sport':'CYCLING','functionalThresholdPower':201},
           {'sport':'RUNNING','functionalThresholdPower':251}]
    reads=iter([before,after])
    b._api.get_power_zones=lambda:next(reads)
    b._api.request=lambda *a,**k:Response(None)
    with pytest.raises(WriteFailure) as caught:
        execute(b,'update_power_zones',{'expected_account':ACCOUNT,'sport':'CYCLING',
                'changes':{'functionalThresholdPower':201}})
    assert caught.value.outcome['completed_requests'][0]['path']=='/biometric-service/powerZones'
    assert not caught.value.outcome['verified']


def test_cycling_ftp_reports_observed_ski_linkage_explicitly():
    b=backend()
    before=[{'sport':'CYCLING','functionalThresholdPower':200},
            {'sport':'CROSS_COUNTRY_SKIING','functionalThresholdPower':160}]
    after=[{'sport':'CYCLING','functionalThresholdPower':201},
           {'sport':'CROSS_COUNTRY_SKIING','functionalThresholdPower':161}]
    reads=iter([before,after]);b._api.get_power_zones=lambda:next(reads)
    b._api.request=lambda *a,**k:Response(None)
    out=execute(b,'update_power_zones',{'expected_account':ACCOUNT,'sport':'CYCLING',
                'changes':{'functionalThresholdPower':201}})
    assert out['verified']
    assert out['data']['linked_profile_changes']==[{'sport':'CROSS_COUNTRY_SKIING',
        'changes':{'functionalThresholdPower':{'before':160,'after':161}}}]


def test_write_status_is_reported_without_body_and_without_retry():
    from garminconnect import GarminConnectConnectionError
    b = backend()
    def failed(method, domain, path, **kwargs):
        b._api.calls.append((method,path))
        raise GarminConnectConnectionError('API Error 429 - secret-token private-response')
    b._api.request = failed
    with pytest.raises(WriteFailure) as caught:
        execute(b, 'unschedule_workout', {'expected_account':ACCOUNT, 'schedule_id':11})
    outcome = caught.value.outcome
    assert outcome['http_status'] == 429
    assert outcome['verified'] is False
    assert outcome['completed_requests'] == []
    assert 'secret-token' not in str(outcome)
    assert b._api.calls == [('DELETE','/workout-service/schedule/11')]


def test_measurement_system_write_sends_only_preference():
    from copy import deepcopy
    b=backend()
    before={'userData':{'measurementSystem':'statute_us','weight':None},'unknown':{'preserve':True}}
    after=deepcopy(before);after['userData']['measurementSystem']='metric'
    reads=iter([before,after]);b._api.get_user_profile=lambda:next(reads)
    sent=[]
    def request(method,domain,path,**kwargs):
        sent.append((method,path,kwargs));return Response(None)
    b._api.request=request
    result=execute(b,'update_measurement_system',{'expected_account':ACCOUNT,'measurement_system':'metric'})
    assert result['verified']
    assert sent==[('PUT','/userprofile-service/userprofile/user-settings',{'json':{'userData':{'measurementSystem':'metric'}}})]
    assert before['userData']['measurementSystem']=='statute_us'


def test_unit_change_does_not_hide_unrelated_profile_changes():
    b=backend()
    reads=iter([{'userData':{'measurementSystem':'statute_us','weight':None}},
                {'userData':{'measurementSystem':'metric','weight':70000}}])
    b._api.get_user_profile=lambda:next(reads)
    b._api.request=lambda *a,**k:Response(None)
    with pytest.raises(WriteFailure) as caught:
        execute(b,'update_measurement_system',{'expected_account':ACCOUNT,'measurement_system':'metric'})
    assert not caught.value.outcome['verified']
    assert len(caught.value.outcome['completed_requests'])==1
