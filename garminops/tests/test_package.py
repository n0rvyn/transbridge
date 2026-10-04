"""Release boundary checks using fake secrets, never personal credentials."""
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('packager', ROOT / 'scripts/package_garmin.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


@pytest.fixture
def project(tmp_path):
    source = tmp_path / 'garminops'
    for name in packager.RELEASE_FILES:
        target = packager.release_input(tmp_path, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(packager.release_input(ROOT, name), target)
    return tmp_path


def test_release_excludes_private_files_at_every_level(project):
    fake_secret = b'FAKE-CREDENTIAL-RELEASE-TEST'
    source = project / 'garminops'
    for folder in (project, source, source / 'src/garminops', source / 'skills/garminops'):
        for name in ('.env', '.env.local', 'garmin_tokens.json', 'oauth1_token.json',
                     'oauth2_token.json', 'private-response.json'):
            (folder / name).write_bytes(fake_secret)
    archive = packager.package(project)
    with zipfile.ZipFile(archive) as package:
        assert set(package.namelist()) == {f'garminops/{name}' for name in packager.RELEASE_FILES}
        assert all(fake_secret not in package.read(name) for name in package.namelist())
    assert all(fake_secret not in path.read_bytes()
               for path in (project / 'dist/garminops').rglob('*') if path.is_file())


@pytest.mark.parametrize('linked_directory', [False, True])
def test_reject_links_before_touching_existing_release(project, linked_directory):
    packager.package(project)
    archive = project / 'dist/garminops-dev.zip'
    before = archive.read_bytes()
    target = project / 'garminops' / ('skills' if linked_directory else 'plugin.json')
    moved = project / 'outside-input'
    target.rename(moved)
    target.symlink_to(moved, target_is_directory=linked_directory)
    with pytest.raises(ValueError, match='symbolic link'):
        packager.package(project)
    assert archive.read_bytes() == before


def test_release_covers_runtime_and_skill_files_and_entrypoint(project):
    source = ROOT / 'garminops'
    runtime = {str(path.relative_to(source)) for path in (source / 'src').rglob('*.py')}
    skills = {str(path.relative_to(source)) for path in (source / 'skills').rglob('*') if path.is_file()}
    assert runtime | skills <= set(packager.RELEASE_FILES)
    packager.package(project)
    stage = project / 'dist/garminops'
    server = json.loads((stage / 'mcp.json').read_text())['mcpServers']['garmin']
    assert server['args'] == ['run', '--locked', '--project', '${PLUGIN_ROOT}', 'garminops', 'serve']
    assert server['cwd'] == '${PLUGIN_ROOT}'
    assert (stage / 'src/garminops/read_methods.json').is_file()


def test_release_excludes_private_logs(project):
    marker = b'FAKE-PRIVATE-VERIFICATION-LOG'
    for base in (project, project / 'garminops'):
        log = base / 'logs' / 'validation' / 'session.md'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes(marker)
    archive = packager.package(project)
    with zipfile.ZipFile(archive) as package:
        assert all('logs' not in Path(name).parts for name in package.namelist())
        assert all(marker not in package.read(name) for name in package.namelist())
    assert all(marker not in path.read_bytes()
               for path in (project / 'dist/garminops').rglob('*') if path.is_file())


@pytest.mark.parametrize('name', ['logs/session.md', 'docs/logs/session.md', '../logs/session.md', 'AGENTS.override.md', 'docs/AGENTS.override.md'])
def test_release_rejects_explicit_log_inputs_before_output(project, monkeypatch, name):
    monkeypatch.setattr(packager, 'RELEASE_FILES', (*packager.RELEASE_FILES, name))
    with pytest.raises(ValueError, match='Private log or unsafe release input'):
        packager.package(project)
    assert not (project / 'dist').exists()


def test_release_excludes_private_account_override(project):
    marker = b'FAKE-PRIVATE-ACCOUNT-RULE'
    for base in (project, project / 'garminops'):
        (base / 'AGENTS.override.md').write_bytes(marker)
    archive = packager.package(project)
    with zipfile.ZipFile(archive) as package:
        assert all('AGENTS.override.md' not in Path(name).parts for name in package.namelist())
        assert all(marker not in package.read(name) for name in package.namelist())
    assert all(marker not in path.read_bytes()
               for path in (project / 'dist/garminops').rglob('*') if path.is_file())


def test_release_includes_matching_mit_license_and_metadata(project):
    import tomllib
    canonical = (ROOT / 'LICENSE').read_bytes()
    assert (ROOT / 'garminops/LICENSE').read_bytes() == canonical
    archive = packager.package(project)
    with zipfile.ZipFile(archive) as package:
        assert package.read('garminops/LICENSE') == canonical
        manifest = json.loads(package.read('garminops/plugin.json'))
        metadata = tomllib.loads(package.read('garminops/pyproject.toml').decode())['project']
        assert manifest['license'] == metadata['license'] == 'MIT'
        assert metadata['license-files'] == ['LICENSE']
    assert (project / 'dist/garminops/LICENSE').read_bytes() == canonical
