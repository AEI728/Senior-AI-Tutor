"""Package reviewable source, excluding dependencies, secrets and runtime databases."""
from pathlib import Path
import zipfile
import os

root = Path(__file__).resolve().parents[1]
destination = root / 'artifacts/packages/xiaoban-source.zip'
destination.parent.mkdir(parents=True, exist_ok=True)
excluded = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', '.mypy_cache', 'backups', 'uploads', 'artifacts',
            '.ruff_cache', 'dist', 'test-results', 'playwright-report', 'live-test-results'}
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
    for folder, directories, filenames in os.walk(root):
        directories[:] = [d for d in directories if d not in excluded]
        for filename in filenames:
            path = Path(folder) / filename
            relative = path.relative_to(root)
            if path.name.startswith('.env') and path.name != '.env.example':
                continue
            if path.suffix in ('.db', '.log') or '.db-' in path.name:
                continue
            archive.write(path, Path(root.name) / relative)
print(destination)
