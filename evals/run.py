"""Held-out intent evaluation. Behavioral/fault scenarios use the integration and E2E suites."""
import argparse
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--provider', choices=['mock', 'live'], required=True)
args = parser.parse_args()
sys.path.insert(0, str(root / 'apps/api'))
from app.schemas import Context  # noqa: E402
from app.agent import mock_plan, model_plan  # noqa: E402
from app.config import settings  # noqa: E402
if args.provider == 'live' and settings().llm_provider == 'mock':
    raise SystemExit('BLOCKED_EXTERNAL_DEPENDENCY: real provider required')
report = {'time_utc': datetime.now(timezone.utc).isoformat(), 'provider': args.provider,
          'model': (settings().deepseek_model if settings().llm_provider=='deepseek' else settings().openai_model) if args.provider == 'live' else 'deterministic-rules-v2',
          'prompt_version': 'base-v1/companion-v2', 'results': []}
for line in (root / 'evals/cases/holdout.jsonl').read_text('utf-8').splitlines():
    case = json.loads(line)
    context = Context.model_validate(case.get('context', {}))
    plan = mock_plan(case['input'], context) if args.provider == 'mock' else model_plan(case['input'], context,
        [{'id':'home-gardening','name':'家庭园艺'},{'id':'calligraphy','name':'书法入门'},{'id':'photography','name':'手机摄影'},{'id':'music','name':'节奏入门'}],{})[0]
    passed = plan.intent == case['expected']['intent']
    report['results'].append({'id': case['id'], 'expected': case['expected']['intent'], 'actual': plan.intent, 'passed': passed})
output = root / f'docs/evals/intent-{args.provider}.json'
output.parent.mkdir(exist_ok=True, parents=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
count = sum(r['passed'] for r in report['results'])
print(f"Intent holdout: {count}/{len(report['results'])}; {output}")
raise SystemExit(0 if count == len(report['results']) else 1)
