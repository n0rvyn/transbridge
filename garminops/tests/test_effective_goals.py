import pytest
from pydantic import ValidationError

from garminops.backend import Backend, make_api, UpstreamResponseError


@pytest.mark.parametrize('day', ['2026-02-30', '20261002', '2026-W40-5', '../settings', '', 0, None])
def test_invalid_goal_date_rejected_before_login(day):
    with pytest.raises(ValidationError):
        Backend('com').read('get_effective_goals', {'day': day})


@pytest.mark.parametrize('sample', [[], [{'goalType': 'STEPS', 'goalValue': 10000.0,
                                       'newField': None}]])
def test_effective_goal_date_and_original_response(monkeypatch, sample):
    api = make_api('com')
    calls = []
    def request(path):
        calls.append(path)
        return sample
    monkeypatch.setattr(api, 'connectapi', request)
    assert api.get_effective_goals('2024-02-29') == sample
    assert calls == ['/goal-service/goal/user/effective/2024-02-29']


@pytest.mark.parametrize('sample', [None, {}, ['error'], [{'goalType': 'STEPS'}],
    [{'goalType': 'STEPS', 'goalValue': True}], [{'goalType': 1, 'goalValue': 100}]])
def test_effective_goals_reject_malformed_response(monkeypatch, sample):
    api = make_api('com')
    monkeypatch.setattr(api, 'connectapi', lambda path: sample)
    with pytest.raises(UpstreamResponseError):
        api.get_effective_goals('2026-10-02')
