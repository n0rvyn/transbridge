from copy import deepcopy
from threading import RLock
from types import SimpleNamespace

import pytest
from garminconnect import GarminConnectNotFoundError
from garminops.backend import ConnectorGarmin, UpstreamResponseError
from garminops.policy import ContractUnverified, PolicyDenied, check_request, write_intent
from garminops.writes import execute, WriteFailure


class NoteAPI:
    display_name = 'test'
    full_name = 'Test'

    def __init__(self):
        self.client = self
        self.rows = {}
        self.calls = []
        self.hide_calendar = False
        self.ignore_delete = False

    def get_calendar_note(self, note_id):
        if note_id not in self.rows:
            raise GarminConnectNotFoundError('API Error 404')
        return deepcopy(self.rows[note_id])

    def get_scheduled_workouts(self, year, month):
        rows = [] if self.hide_calendar else [dict(id=r['id'], date=r['date'], itemType='note')
            for r in self.rows.values() if r['date'].startswith(f'{year:04}-{month:02}')]
        return {'calendarItems': rows}

    def request(self, method, domain, path, **kwargs):
        payload = kwargs.get('json')
        check_request(method, path, named_read=False, payload=payload)
        self.calls.append((method, path, deepcopy(payload)))
        if method == 'POST':
            self.rows[1] = payload | {'id': 1}
        elif method == 'PUT':
            self.rows[1] = deepcopy(payload)
        elif not self.ignore_delete:
            del self.rows[1]
        data = deepcopy(self.rows.get(1))
        return SimpleNamespace(content=b'{}', json=lambda: data)


def backend():
    return SimpleNamespace(_api=NoteAPI(), _lock=RLock(), region='com', read=lambda *a: 'Test')


def create(b):
    return execute(b, 'create_calendar_note', dict(expected_account='test', name='Test',
                    content='Plan', day='2099-10-10'))


def test_calendar_note_roundtrip_and_cross_month_move():
    b = backend()
    assert create(b)['verified']
    changed = execute(b, 'update_calendar_note', dict(expected_account='test', note_id=1,
                      changes={'date': '2099-11-10', 'noteName': 'Moved'}))
    assert changed['data']['date'] == '2099-11-10'
    assert execute(b, 'delete_calendar_note', dict(expected_account='test', note_id=1))['verified']


@pytest.mark.parametrize('operation', ['update_calendar_note', 'delete_calendar_note'])
@pytest.mark.parametrize('extra', [{'date': '2020-01-01'}, {'activityId': 23}, {'trainingPlanId': 34}])
def test_historical_or_mixed_note_never_written(operation, extra):
    b = backend()
    b._api.rows[1] = dict(id=1, noteName='Test', content='Plan', date='2099-10-10') | extra
    args = dict(expected_account='test', note_id=1)
    if operation == 'update_calendar_note':
        args['changes'] = {'noteName': 'Changed'}
    with pytest.raises((ValueError, ContractUnverified)):
        execute(b, operation, args)
    assert not b._api.calls


def test_wrong_account_does_not_read_note():
    b = backend()
    b._api.get_calendar_note = lambda _: pytest.fail('Unauthorized resource read')
    with pytest.raises(PolicyDenied):
        execute(b, 'delete_calendar_note', dict(expected_account='other', note_id=1))
    assert not b._api.calls


def test_calendar_absence_after_create_reports_id_and_does_not_retry():
    b = backend(); b._api.hide_calendar = True
    with pytest.raises(WriteFailure) as error:
        create(b)
    assert error.value.outcome['completed_requests'][0]['response']['id'] == 1
    assert len(b._api.calls) == 1


def test_ignored_delete_does_not_report_success():
    b = backend(); create(b); b._api.ignore_delete = True
    with pytest.raises(WriteFailure):
        execute(b, 'delete_calendar_note', dict(expected_account='test', note_id=1))


def test_note_route_and_payload_ids_must_agree():
    with pytest.raises(PolicyDenied):
        with write_intent('PUT', '/calendar-service/note/1',
                         dict(id=2, noteName='Test', content='', date='2099-10-10')):
            pytest.fail('Mismatched ID accepted')
    with pytest.raises(PolicyDenied):
        with write_intent('PUT', '/trainingplan-service/trainingplan/scheduled/notes/1', {}):
            pytest.fail('Training-plan note accepted')


def test_note_reader_preserves_fields_and_rejects_wrong_resource():
    row = dict(id=1, noteName='Test', content='Plan', date='2099-10-10', extension=None)
    api = SimpleNamespace(connectapi=lambda path: deepcopy(row))
    assert ConnectorGarmin.get_calendar_note(api, 1) == row
    with pytest.raises(UpstreamResponseError):
        ConnectorGarmin.get_calendar_note(api, 2)
