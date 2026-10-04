import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from garminops import connection
from garminops.backend import Backend


def test_selected_region_one_at_a_time(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME',str(tmp_path))
    assert connection.selected_region()=='com'
    connection.activate_region('cn')
    assert connection.selected_region()=='cn'
    connection.activate_region('com')
    assert connection.selected_region()=='com'
    with pytest.raises(ValueError): connection.activate_region('other')
    assert connection.selected_region()=='com'


def test_explicit_login_never_restores_existing_account(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME',str(tmp_path))
    old=connection.session_directory('cn');old.mkdir(parents=True)
    (old/'garmin_tokens.json').write_text('old-account')
    seen=[]
    class API:
        display_name='new-account-id'; full_name='New'; password=None
        def __init__(self): self.client=self
        def login(self,path):
            assert Path(path)!=old
            seen.append(Path(path))
        def dump(self,path):
            Path(path,'garmin_tokens.json').write_text('new-account')
    monkeypatch.setattr(connection,'make_api',lambda *a,**k: API())
    assert connection.login_and_save('cn','test@example.invalid','hidden',lambda:'') ['account_id']=='new-account-id'
    assert seen[0]==seen[1]
    assert not seen[0].exists()
    assert (old/'garmin_tokens.json').read_text()=='new-account'
    assert connection.selected_region()=='cn'


def test_failed_login_preserves_active_region_and_saved_session(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME',str(tmp_path))
    connection.activate_region('com')
    old=connection.session_directory('cn');old.mkdir(parents=True)
    (old/'garmin_tokens.json').write_text('unchanged')
    class API:
        password=None
        def login(self,path): raise RuntimeError('login failure')
    monkeypatch.setattr(connection,'make_api',lambda *a,**k:API())
    with pytest.raises(RuntimeError): connection.login_and_save('cn','test@example.invalid','hidden',lambda:'')
    assert connection.selected_region()=='com'
    assert (old/'garmin_tokens.json').read_text()=='unchanged'


def test_running_backend_reloads_replaced_session(tmp_path, monkeypatch):
    import garminops.backend as module
    monkeypatch.setenv('HOME',str(tmp_path))
    b=Backend('com');b.session_dir.mkdir(parents=True)
    token=b.session_dir/'garmin_tokens.json';token.write_text('old')
    class API:
        def login(self,path): self.name=Path(path,'garmin_tokens.json').read_text()
        def get_full_name(self): return self.name
    monkeypatch.setattr(module,'make_api',lambda *a,**k:API())
    assert b.read('get_full_name',{})=='old'
    token.write_text('new-account')
    assert b.read('get_full_name',{})=='new-account'


@pytest.mark.parametrize('change', ['delete', 'replace'])
def test_status_does_not_verify_missing_or_replaced_credentials(tmp_path, monkeypatch, change):
    import garminops.backend as module
    monkeypatch.setenv('HOME', str(tmp_path))
    backend = Backend('com')
    backend.session_dir.mkdir(parents=True)
    token = backend.session_dir/'garmin_tokens.json'
    token.write_text('old')
    class API:
        def login(self, path): self.name = Path(path, 'garmin_tokens.json').read_text()
        def get_full_name(self): return self.name
    monkeypatch.setattr(module, 'make_api', lambda *a, **k: API())
    assert not backend.status()['session_verified_in_process']
    assert backend.read('get_full_name', {}) == 'old'
    assert backend.status()['session_verified_in_process']
    if change == 'delete':
        token.unlink()
    else:
        token.write_text('replacement-account')
    status = backend.status()
    assert status['session_file_present'] == (change == 'replace')
    assert not status['session_verified_in_process']
    if change == 'delete':
        with pytest.raises(module.LoginRequired):
            backend.read('get_full_name', {})
    else:
        assert backend.read('get_full_name', {}) == 'replacement-account'
        assert backend.status()['session_verified_in_process']


def test_login_resolves_system_temp_symlink(tmp_path, monkeypatch):
    from tempfile import TemporaryDirectory
    from garminconnect.client import token_file_path
    monkeypatch.setenv('HOME', str(tmp_path))
    actual = tmp_path/'actual'; actual.mkdir()
    alias = tmp_path/'alias'; alias.symlink_to(actual, target_is_directory=True)
    monkeypatch.setattr(connection, 'TemporaryDirectory',
        lambda **kwargs: TemporaryDirectory(dir=alias, **kwargs))
    class API:
        display_name='test-account'; full_name='Test'; password=None
        def __init__(self): self.client=self
        def login(self, path): token_file_path(path)
        def dump(self, path): token_file_path(path).write_text('test-session')
    monkeypatch.setattr(connection, 'make_api', lambda *a, **k: API())
    assert connection.login_and_save('cn', 'private-email', 'private-password', lambda:'')['region']=='cn'


def test_login_error_reports_stage_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    class API:
        password='secret'
        def login(self, path): raise ValueError('secret password token email')
    api=API()
    monkeypatch.setattr(connection, 'make_api', lambda *a, **k: api)
    with pytest.raises(connection.LoginFailure) as caught:
        connection.login_and_save('cn', 'email', 'secret', lambda:'')
    assert str(caught.value)=='authenticate and read profile: ValueError'
    assert api.password is None


def test_unit_system_reads_current_profile_instead_of_login_cache(tmp_path, monkeypatch):
    import garminops.backend as module
    monkeypatch.setenv('HOME', str(tmp_path))
    backend=Backend('com');backend.session_dir.mkdir(parents=True)
    (backend.session_dir/'garmin_tokens.json').write_text('fixture')
    class API:
        def login(self,path): pass
        def get_unit_system(self): pytest.fail('Login-time cache used')
        def get_user_profile(self): return {'userData':{'measurementSystem':self.current}}
        current='statute_us'
    api=API();monkeypatch.setattr(module,'make_api',lambda *a,**k:api)
    assert backend.read('get_unit_system',{})=='statute_us'
    api.current='metric'
    assert backend.read('get_unit_system',{})=='metric'
