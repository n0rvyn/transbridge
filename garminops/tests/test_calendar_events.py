from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from garminops.backend import ConnectorGarmin, UpstreamResponseError, input_model


def sample():
    # Shape observed from the authorized private event prototype; no account identifiers.
    return dict(id=1, eventName='Synthetic', date='2099-10-10', eventType='running',
        eventPrivacy=dict(label='PRIVATE', isShareable=False, isDiscoverable=False),
        eventCustomization=dict(customGoal=None, isPrimaryEvent=False,
            associatedWithActivityId=None, isTrainingEvent=False, isGoalMet=None,
            trainingPlanId=None, trainingPlanType=None),
        completionTarget=dict(value=1.0, unit='mile', unitType='distance'),
        extension={'unknown': None})


def test_event_reader_preserves_associations_and_unknown_fields():
    row = sample()
    row['eventCustomization']['associatedWithActivityId'] = 123
    calls = []
    def read(path):
        calls.append(path)
        return deepcopy(row)
    result = ConnectorGarmin.get_calendar_event(SimpleNamespace(connectapi=read), 1)
    assert result == row
    assert calls == ['/calendar-service/event/1']


@pytest.mark.parametrize('change', [dict(id=2), dict(id=True), dict(eventName=None),
    dict(eventPrivacy=None), dict(eventCustomization=None)])
def test_event_reader_rejects_mismatched_or_malformed_responses(change):
    api = SimpleNamespace(connectapi=lambda path: sample() | change)
    with pytest.raises(UpstreamResponseError):
        ConnectorGarmin.get_calendar_event(api, 1)


@pytest.mark.parametrize('value', [True, 0, -1, '1', '../note/1'])
def test_event_tool_rejects_invalid_ids_before_dispatch(value):
    with pytest.raises(ValidationError):
        input_model('get_calendar_event')(event_id=value)

from threading import RLock
from garminconnect import GarminConnectNotFoundError
from garminops.events import event_payload, editable_event
from garminops.policy import ContractUnverified, PolicyDenied, check_request, write_intent
from garminops.writes import execute, WriteFailure


def definition():
    return dict(eventName='Synthetic', date='2099-10-10', eventType='running',
        eventTimeLocal=None, race=True, official=False, eventPrivacy={'label': 'PRIVATE'},
        courseId=None, courseName='', location='',
        completionTarget={'value': 1, 'unit': 'mile', 'unitType': 'distance'},
        locationStartPoint=None, note='Synthetic plan', url='', imageUrl='')


def response(p):
    row = deepcopy(p)
    row.pop('official'); row.pop('imageUrl')
    row.update(id=1, groupId=None, registrationUrl=None, workoutId=None,
        eventImageUUID=None, shareableEventUuid=None, eventRef=None, statuses=None,
        workoutName=None, eventImageURLs=None, subscribersCount=None, subscribed=None,
        eventOrganizer=True, provider='gc-discoverable-events', courseName=None,
        url=p['url'] or None,
        eventPrivacy={'label':'PRIVATE', 'isShareable':False, 'isDiscoverable':False},
        eventCustomization=dict(customGoal=None, isPrimaryEvent=False,
            associatedWithActivityId=None, isTrainingEvent=False, isGoalMet=None,
            trainingPlanId=None, trainingPlanType=None, enrollmentTime='2026-10-02T00:00:00.000'))
    return row


class EventAPI:
    display_name = 'test'
    full_name = 'Test'

    def __init__(self):
        self.client = self
        self.rows = {}
        self.calls = []
        self.ignore_delete = False
        self.hide_calendar = False
        self.change_unrelated = False

    def get_calendar_event(self, event_id):
        if event_id not in self.rows:
            raise GarminConnectNotFoundError('API Error 404')
        return deepcopy(self.rows[event_id])

    def get_scheduled_workouts(self, year, month):
        return {'calendarItems': [] if self.hide_calendar else [
            dict(id=r['id'], date=r['date'], title=r['eventName'], itemType='event')
            for r in self.rows.values() if r['date'].startswith(f'{year:04}-{month:02}')]}

    def request(self, method, domain, path, **kwargs):
        payload = kwargs.get('json')
        check_request(method, path, named_read=False, payload=payload)
        self.calls.append((method, path, deepcopy(payload)))
        if method in ('POST', 'PUT'):
            self.rows[1] = response(payload)
            if method == 'PUT' and self.change_unrelated:
                self.rows[1]['provider'] = 'unexpected'
        elif not self.ignore_delete:
            del self.rows[1]
        data = deepcopy(self.rows.get(1))
        return SimpleNamespace(content=b'{}', json=lambda: data)


def backend():
    return SimpleNamespace(_api=EventAPI(), _lock=RLock(), region='com', read=lambda *a: 'Test')


def create(b):
    return execute(b, 'create_calendar_event', dict(expected_account='test', event=definition()))


def test_event_write_roundtrip_with_cross_month_move():
    b=backend()
    assert create(b)['verified']
    result=execute(b, 'update_calendar_event', dict(expected_account='test',event_id=1,
        changes={'eventName':'Moved', 'date':'2099-11-10'}))
    assert result['verified'] and result['data']['date']=='2099-11-10'
    assert execute(b,'delete_calendar_event',dict(expected_account='test',event_id=1))['verified']
    assert not b._api.rows
    assert all('eventCustomization' not in (p or {}) for _,_,p in b._api.calls)


@pytest.mark.parametrize('operation', ['update_calendar_event','delete_calendar_event'])
@pytest.mark.parametrize('field,value', [('associatedWithActivityId',12),('trainingPlanId',13),
    ('trainingPlanType','COACH'),('isGoalMet',True),('customGoal',{}),
    ('isPrimaryEvent',True),('isTrainingEvent',True)])
def test_associated_or_recorded_events_never_written(operation,field,value):
    b=backend();b._api.rows[1]=response(definition())
    b._api.rows[1]['eventCustomization'][field]=value
    args=dict(expected_account='test',event_id=1)
    if operation=='update_calendar_event':args['changes']={'eventName':'Changed'}
    with pytest.raises(ContractUnverified):execute(b,operation,args)
    assert not b._api.calls


@pytest.mark.parametrize('change', [dict(date='2020-01-01'),dict(groupId=1),dict(statuses=['OFFICIAL']),
    dict(unknown=None),dict(eventOrganizer=False),dict(eventCustomization={})])
def test_event_delete_rejects_unverified_or_historical_state(change):
    b=backend();b._api.rows[1]=response(definition())|change
    with pytest.raises(ContractUnverified):
        execute(b,'delete_calendar_event',dict(expected_account='test',event_id=1))
    assert not b._api.calls


def test_wrong_account_cannot_read_event():
    b=backend();b._api.get_calendar_event=lambda _:pytest.fail('Unauthorized event read')
    with pytest.raises(PolicyDenied):
        execute(b,'delete_calendar_event',dict(expected_account='other',event_id=1))


def test_create_calendar_absence_keeps_returned_id_without_retry():
    b=backend();b._api.hide_calendar=True
    with pytest.raises(WriteFailure) as caught:create(b)
    assert caught.value.outcome['completed_requests'][0]['response']['id']==1
    assert len(b._api.calls)==1


def test_event_update_checks_unrelated_fields():
    b=backend();create(b);b._api.change_unrelated=True
    with pytest.raises(WriteFailure):
        execute(b,'update_calendar_event',dict(expected_account='test',event_id=1,changes={'eventName':'Changed'}))


def test_ignored_event_delete_fails_verification():
    b=backend();create(b);b._api.ignore_delete=True
    with pytest.raises(WriteFailure):
        execute(b,'delete_calendar_event',dict(expected_account='test',event_id=1))


@pytest.mark.parametrize('path', ['/calendar-service/group/1/event','/calendar-service/event/1/subscription',
    '/calendar-service/event/1/status/OFFICIAL','/calendar-service/event/1/customization'])
def test_event_side_effect_routes_not_permitted(path):
    with pytest.raises(PolicyDenied):
        with write_intent('PUT',path,{}):pytest.fail('Unregistered route accepted')


def test_event_outbound_definition_rejects_results_and_id_mismatch():
    with pytest.raises(ContractUnverified):
        with write_intent('POST','/calendar-service/event',definition()|{'eventCustomization':{}}):
            pytest.fail('Results accepted')
    with pytest.raises(PolicyDenied):
        with write_intent('PUT','/calendar-service/event/1',definition()|{'id':2}):
            pytest.fail('Wrong ID accepted')


@pytest.mark.parametrize('target', [{'value':True,'unit':'mile','unitType':'distance'},
    {'value':float('nan'),'unit':'mile','unitType':'distance'},
    {'value':1,'unit':'second','unitType':'distance'}])
def test_event_target_validation(target):
    with pytest.raises(ValueError):event_payload(definition()|{'completionTarget':target})
