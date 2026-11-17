import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
lines = (root / 'docs/implementation.md').read_text('utf-8').splitlines()
cases = []
for line in lines:
    if line.startswith('| BC'):
        columns = [c.strip() for c in line.split('|')[1:-1]]
        cases.append({'id': columns[0], 'input': columns[1], 'expected': {'description': columns[2]},
                      'role': 'tutor' if 11 <= int(columns[0][2:]) <= 19 else 'companion',
                      'context': {}, 'risk': 'safety' if columns[0] == 'BC19' else 'normal'})
path = root / 'evals/cases/bad_cases.jsonl'
path.write_text(''.join(json.dumps(c, ensure_ascii=False)+'\n' for c in cases), 'utf-8')
assert len(cases) == 24
