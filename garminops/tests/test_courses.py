import pytest
from garminops.backend import make_api, UpstreamResponseError


@pytest.mark.parametrize('data', [[], [{'courseId': 123, 'unknownField': {'keep': True}}]])
def test_course_reader_preserves_response_and_uses_fixed_endpoint(monkeypatch, data):
    api = make_api('com')
    calls = []
    def request(path):
        calls.append(path)
        return data
    monkeypatch.setattr(api, 'connectapi', request)
    assert api.get_courses() == data
    assert calls == ['/course-service/course']


@pytest.mark.parametrize('data', [None, {'error': 'upstream failure'}, 'unexpected html'])
def test_course_reader_does_not_turn_invalid_response_into_empty_success(monkeypatch, data):
    api = make_api('com')
    monkeypatch.setattr(api, 'connectapi', lambda path: data)
    with pytest.raises(UpstreamResponseError):
        api.get_courses()


def test_course_detail_preserves_live_shape_nulls_and_unknown_fields(monkeypatch):
    api=make_api('com');calls=[]
    detail={'courseId':123,'coursePoints':None,'courseLines':[{'points':None}],
            'geoPoints':[{'latitude':0.0,'longitude':0.0,'elevation':0.0}],
            'unknown':{'preserve':True}}
    def read(path):calls.append(path);return detail
    monkeypatch.setattr(api,'connectapi',read)
    assert api.get_course(123)==detail
    assert calls==['/course-service/course/123']


@pytest.mark.parametrize('value', [True,0,-1,'123','../activity/1',1.5])
def test_course_id_is_validated_before_any_login_or_request(value):
    from garminops.backend import Backend
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Backend('com').read('get_course', {'course_id':value})


@pytest.mark.parametrize('value', [[],None,{'courseId':124},{'courseId':'123'},{'error':'failed'}])
def test_course_detail_rejects_wrong_resource_or_structure(monkeypatch,value):
    api=make_api('com');monkeypatch.setattr(api,'connectapi',lambda path:value)
    with pytest.raises(UpstreamResponseError):api.get_course(123)
