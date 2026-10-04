import pytest

from garminops.backend import make_api, UpstreamResponseError


def test_display_settings_preserve_nested_formats_nulls_and_extensions(monkeypatch):
    api = make_api('com')
    sample = {'measurementSystem': 'metric', 'timeFormat': {'formatKey': 'time_24'},
              'dateFormat': {'formatKey': 'dd_mm_yyyy'}, 'golfSpeedUnit': None,
              'hydrationContainers': [], 'newPreference': {'keep': True}}
    calls = []
    def request(path):
        calls.append(path)
        return sample
    monkeypatch.setattr(api, 'connectapi', request)
    assert api.get_userprofile_settings() == sample
    assert calls == ['/userprofile-service/userprofile/settings']


@pytest.mark.parametrize('sample', [None, [], {}, {'error': 'failed'},
    {'measurementSystem': 'metric', 'timeFormat': '24h', 'dateFormat': {}},
    {'measurementSystem': 'metric', 'timeFormat': {}, 'dateFormat': None}])
def test_display_settings_reject_invalid_upstream_shapes(monkeypatch, sample):
    api = make_api('com')
    monkeypatch.setattr(api, 'connectapi', lambda path: sample)
    with pytest.raises(UpstreamResponseError):
        api.get_userprofile_settings()
