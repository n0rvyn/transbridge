import inspect

import pytest
from garminconnect.client import Client
from pydantic import ValidationError

from garminops.backend import Backend, GuardedClient, READ_METHODS, input_model, make_api
from garminops.policy import ContractUnverified, PolicyDenied, clean_path


@pytest.mark.parametrize("method,path", [
    ("PUT", "/activity-service/activity/123"),
    ("DELETE", "/activity-service/activity/123"),
    ("POST", "/upload-service/upload"),
    ("POST", "/weight-service/user-weight"),
    ("PUT", "/wellness-service/wellness/hydrationLog"),
    ("POST", "/periodichealth-service/menstrualcycle/dailylog/2026-10-02"),
    ("PUT", "/gear-service/gear/link/abc/activity/123"),
    ("PUT", "/gear-service/activity/v2/123/associated-gear"),
    ("DELETE", "/gear-service/activity/v2/123/associated-gear"),
    ("POST", "/gear-service/gear/v2/00000000-0000-4000-8000-000000000001/activity-type-association"),
    ("POST", "/gear-service/collection/00000000-0000-4000-8000-000000000001/activity-type-association"),
    ("POST", "/graphql-gateway/graphql"),
])
def test_mutations_never_reach_upstream(monkeypatch, method, path):
    sent = []
    monkeypatch.setattr(Client, "_run_request", lambda *a, **k: sent.append((a, k)))
    with pytest.raises(PolicyDenied):
        GuardedClient()._run_request(method, path)
    assert sent == []


@pytest.mark.parametrize("path", [
    "https://example.com/x", "//example.com/x", "/foo/../activity-service/x",
    "/foo/%252e%252e/activity-service/x", "/foo?method=DELETE", "/foo#x",
    "/foo\\bar", "/foo/%0abar", "/foo/..;x/bar", "/foo//bar",
])
def test_path_bypasses_rejected(path):
    with pytest.raises(PolicyDenied):
        clean_path(path)


def test_unverified_plan_write_is_not_silently_enabled(monkeypatch):
    monkeypatch.setattr(Client, "_run_request", lambda *a, **k: pytest.fail("sent"))
    with pytest.raises(ContractUnverified):
        GuardedClient().post("connectapi", "/workout-service/workout", json={})


def test_all_reads_have_strict_input_schemas():
    for name in READ_METHODS:
        assert input_model(name).model_json_schema()["additionalProperties"] is False
    with pytest.raises(ValidationError):
        input_model("get_workouts").model_validate({"method": "DELETE"})


def test_registry_excludes_all_mutations_and_generic_dispatch():
    assert len(READ_METHODS) == len(set(READ_METHODS))
    assert not set(READ_METHODS) & {"connectapi", "query_garmin_graphql", "download", "request_reload", "login"}
    assert all(n.startswith(("get_", "count_", "download_")) for n in READ_METHODS)


def test_region_isolation():
    com, cn = Backend("com"), Backend("cn")
    assert com.session_dir != cn.session_dir
    assert make_api("com").client.domain == "garmin.com"
    assert make_api("cn").client.domain == "garmin.cn"


def test_guard_is_installed_on_real_adapter():
    assert isinstance(make_api("com").client, GuardedClient)
    assert "_run_request" in inspect.getsource(Client.connectapi)


def test_unknown_operation_rejected_before_login():
    with pytest.raises(PolicyDenied):
        Backend().read("delete_activity", {"activity_id": "123"})


def test_get_bodies_and_header_overrides_rejected(monkeypatch):
    monkeypatch.setattr(Client, "_run_request", lambda *a, **k: pytest.fail("sent"))
    with pytest.raises(PolicyDenied):
        GuardedClient()._run_request("GET", "/activity-service/activity/123", headers={"X-HTTP-Method-Override": "DELETE"})


def test_real_sdk_goals_and_download_fixed_headers_reach_transport(monkeypatch):
    from types import SimpleNamespace
    sent=[]
    def request(self, method, path, **kwargs):
        sent.append((method,path,kwargs))
        return SimpleNamespace(status_code=200,content=b'FIT-sample',json=lambda:[])
    monkeypatch.setattr(Client, '_run_request', request)
    api=make_api('com')
    assert api.get_goals()==[]
    assert sent[-1][2]['headers']=={'Sec-Fetch-Site':'same-origin'}
    assert api.download_workout(123)==b'FIT-sample'
    assert sent[-1][2]['headers']=={'Accept':'*/*'}


@pytest.mark.parametrize('headers', [
    {'Accept':'*/*','X-HTTP-Method-Override':'DELETE'},
    {'Authorization':'attacker'}, {'Sec-Fetch-Site':'cross-site'}])
def test_fixed_read_headers_do_not_allow_arbitrary_overrides(monkeypatch,headers):
    monkeypatch.setattr(Client,'_run_request',lambda *a,**k:pytest.fail('sent'))
    with pytest.raises(PolicyDenied):
        GuardedClient()._run_request('GET','/goal-service/goal/goals',headers=headers)


@pytest.mark.parametrize('payload', [
    {'userData':{'weight':70000}},
    {'userData':{'measurementSystem':'metric','weight':70000}},
    {'userData':{'measurementSystem':'metric'},'userSleep':{}},
    {'userData':{'measurementSystem':None}},
])
def test_profile_endpoint_cannot_smuggle_logged_values(monkeypatch,payload):
    from garminops.policy import write_intent
    monkeypatch.setattr(Client,'_run_request',lambda *a,**k:pytest.fail('sent'))
    with pytest.raises(PolicyDenied):
        with write_intent('PUT','/userprofile-service/userprofile/user-settings',payload):
            GuardedClient()._run_request('PUT','/userprofile-service/userprofile/user-settings',json=payload)
