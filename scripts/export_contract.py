import json
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'apps/api'))
from app.main import app  # noqa: E402
path = root / 'docs/api/openapi.snapshot.json'
content = json.dumps(app.openapi(), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
if '--check' in sys.argv:
    if not path.exists() or path.read_text('utf-8') != content:
        raise SystemExit('OpenAPI contract changed: export and regenerate frontend types')
else:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, 'utf-8')
