"""Build the local plugin from an explicit release-file inventory."""
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILES = (
    'LICENSE',
    'plugin.json',
    'mcp.json',
    'pyproject.toml',
    'uv.lock',
    'skills/garminops/SKILL.md',
    'docs/README.md',
    'docs/scope/SCOPE.md',
    'docs/scope/CAPABILITY_INVENTORY.md',
    'docs/research/SOURCE_METHODS.md',
    'docs/research/WEB_CONTRACT_RESEARCH.md',
    'docs/research/inventory.json',
    'docs/research/sources.json',
    'docs/validation/DESKTOP_EVAL.md',
    'docs/validation/LIVE_VERIFICATION.md',
    'docs/validation/TASK_VALIDATION.md',
    'docs/validation/READ_VERIFICATION.json',
    'docs/operations/RUNNING.md',
    'docs/operations/ERROR_DIAGNOSTICS.md',
    *(f'src/garminops/{name}' for name in (
        '__init__.py', 'backend.py', 'cli.py', 'connection.py', 'drafts.py',
        'errors.py', 'policy.py', 'server.py', 'writes.py', 'goals.py', 'events.py', 'gear.py', 'read_methods.json',
    )),
)


def release_input(root: Path, name: str) -> Path:
    return root / name if name.startswith('docs/') else root / 'garminops' / name


def package(root: Path = ROOT) -> Path:
    source = root / 'garminops'
    # Validate every selected file before creating any release output. Do not
    # follow links, including links in a parent directory, into private files.
    for name in RELEASE_FILES:
        if "logs" in Path(name).parts or "AGENTS.override.md" in Path(name).parts or ".." in Path(name).parts or Path(name).is_absolute():
            raise ValueError(f"Private log or unsafe release input: {name}")
        path = release_input(root, name)
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError(f'Release input is a symbolic link: {name}')
        if not path.is_file():
            raise FileNotFoundError(f'Missing release input: {name}')
    dist = root / 'dist'
    dist.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='garmin-build-', dir=dist) as temporary:
        stage = Path(temporary) / 'garminops'
        for name in RELEASE_FILES:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(release_input(root, name), target)
            if name == 'skills/garminops/SKILL.md':
                target.write_text(target.read_text().replace('../../../docs/', '../../docs/'))
            elif name == 'docs/README.md':
                target.write_text(target.read_text().replace('../garminops/skills/', '../skills/'))
        archive = Path(temporary) / 'garminops-dev.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
            for name in sorted(RELEASE_FILES):
                output.write(stage / name, f'garminops/{name}')
        destination = dist / 'garminops'
        if destination.exists():
            shutil.rmtree(destination)
        stage.replace(destination)
        archive.replace(dist / archive.name)
    return dist / 'garminops-dev.zip'


if __name__ == '__main__':
    print(package())
