"""One selected Garmin region; successful explicit login changes selection."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from .backend import make_api, session_directory, error_metadata
from .errors import diagnostics


class LoginFailure(RuntimeError):
    """Safe diagnostic without upstream messages or credential values."""
    def __init__(self, stage, error):
        metadata = error_metadata(error)
        self.diagnostic = {**metadata, **diagnostics(error, stage=stage, operation="login", status=metadata.get("http_status"))}
        self.stage = stage
        self.error_type = type(error).__name__
        super().__init__(f'{stage}: {self.error_type}')


def selected_region() -> str:
    path = Path.home()/'.config/transbridge/garmin/connection.json'
    if not path.exists():
        return 'com'
    region = json.loads(path.read_text())['region']
    if region not in ('com','cn'):
        raise ValueError('Invalid selected Garmin region.')
    return region


def activate_region(region: str) -> None:
    session_directory(region)  # validate before creating anything
    parent = Path.home()/'.config/transbridge/garmin'
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with NamedTemporaryFile(mode='w', dir=parent, delete=False) as f:
        json.dump({'region':region}, f)
        temp = Path(f.name)
    try:
        os.replace(temp, parent/'connection.json')
    finally:
        temp.unlink(missing_ok=True)


def login_and_save(region: str, email: str, password: str, prompt_mfa) -> dict:
    """Never let an old regional session override newly entered credentials."""
    directory = session_directory(region)
    api = make_api(region, email=email, password=password, prompt_mfa=prompt_mfa)
    stage = 'prepare temporary session'
    try:
        with TemporaryDirectory(prefix='garminops-login-') as candidate:
            # macOS /var is a symlink; the SDK rejects symlink ancestors.
            candidate = str(Path(candidate).resolve(strict=True))
            stage = 'authenticate and read profile'
            # Explicit empty path also takes precedence over GARMINTOKENS.
            api.login(candidate)
            stage = 'save temporary session'
            api.client.dump(candidate)
            resumed = make_api(region)
            stage = 'resume fresh session'
            resumed.login(candidate)
            if not resumed.display_name or resumed.display_name != api.display_name:
                raise ValueError('Fresh session identity differs from the login identity.')
            stage = 'save regional session'
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)
            resumed.client.dump(str(directory))
        stage = 'select active region'
        activate_region(region)
        return {'account_id': resumed.display_name, 'name':resumed.full_name, 'region':region}
    except Exception as exc:
        raise LoginFailure(stage, exc) from None
    finally:
        api.password = None
