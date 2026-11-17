"""Cross-platform task runner; records real commands, times and exit codes."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'apps/api'
WEB = ROOT / 'apps/web'
PY = API / ('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
PNPM = shutil.which('pnpm.cmd' if os.name == 'nt' else 'pnpm') or 'pnpm'
ENV = dict(os.environ)


def public_command_value(value):
    value=str(value)
    if value==str(PY):return '${PYTHON}'
    if value==str(PNPM):return '${PNPM}'
    return value.replace(str(ROOT),'${PROJECT_ROOT}').replace(ROOT.as_posix(),'${PROJECT_ROOT}').replace(str(Path.home()),'${USERPROFILE}')


def run(args, cwd=ROOT, env=None):
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run([str(x) for x in args], cwd=cwd, env=env or ENV)
        code = result.returncode
    except FileNotFoundError:
        print('BLOCKED: executable missing: ' + str(args[0]))
        code = 2
    folder = ROOT / 'docs/evals'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'commands.jsonl').open('a', encoding='utf-8') as log:
        log.write(json.dumps({'time_utc': started, 'cwd': public_command_value(cwd), 'command': [public_command_value(x) for x in args],
                              'exit_code': code}, ensure_ascii=False) + '\n')
    if code:
        raise SystemExit(code)


def python(*args, env=None):
    run([PY, *args], API, env)


def task(name):
    if name == 'doctor':
        missing = []
        print('Python: ' + sys.version.split()[0])
        if sys.version_info < (3, 12):
            missing.append('Python >=3.12')
        for command in ('node', 'pnpm', 'uv', 'docker', 'make', 'curl', 'jq', 'ffprobe'):
            found = shutil.which(command)
            print(command + ': ' + (found or 'MISSING'))
            if not found:
                missing.append(command)
        if missing:
            raise SystemExit(2)
    elif name == 'init':
        run(['uv', 'sync', '--frozen'], API)
        run([PNPM, 'install', '--frozen-lockfile'], WEB)
    elif name == 'db-up':
        run(['docker', 'compose', 'up', '-d', '--wait', 'db'])
    elif name == 'migrate':
        python('-m', 'alembic', 'upgrade', 'head')
    elif name == 'seed':
        python('-m', 'app.seed')
    elif name == 'lint':
        python('-m', 'ruff', 'check', 'app', 'tests')
        run([PNPM, 'lint'], WEB)
    elif name == 'typecheck':
        python('-m', 'mypy', 'app')
        run([PNPM, 'typecheck'], WEB)
    elif name in ('test-unit', 'test-integration', 'test-sqlite'):
        env = dict(ENV, APP_ENV='test')
        if name == 'test-integration':
            url = os.environ.get('TEST_DATABASE_URL', '')
            if not url.startswith('postgresql') or 'test' not in url:
                print('BLOCKED: TEST_DATABASE_URL must be a dedicated PostgreSQL test database')
                raise SystemExit(2)
            env['DATABASE_URL'] = url
        else:
            env['DATABASE_URL'] = 'sqlite:///' + (API / 'tests/test.db').as_posix()
        python('-m', 'pytest', 'tests/unit' if name == 'test-unit' else 'tests/integration', '-q', env=env)
    elif name == 'test-web':
        run([PNPM, 'test', '--run'], WEB)
    elif name == 'test':
        for item in ('test-unit', 'test-integration', 'test-web'):
            task(item)
    elif name == 'build':
        python('-c', 'from app.main import app; assert app.title')
        run([PNPM, 'build'], WEB)
    elif name == 'contract':
        run([PY, ROOT / 'scripts/export_contract.py', '--check'])
        run([PNPM, 'exec', 'openapi-typescript', '../../docs/api/openapi.snapshot.json', '--check', '-o', 'src/generated/api.d.ts'], WEB)
    elif name == 'api-dev':
        python('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000')
    elif name == 'web-dev':
        run([PNPM, 'dev', '--host', '127.0.0.1'], WEB)
    elif name in ('dev', 'local', 'preview-local'):
        if name == 'preview-local':
            ENV['DATABASE_URL'] = 'sqlite:///' + (ROOT / 'local-preview.db').as_posix()
            ENV['APP_ENV'] = 'local'
            ENV['LLM_PROVIDER'] = ENV['AUDIO_PROVIDER'] = 'mock'
            ENV['USE_MOCK_LLM'] = 'true'
            ENV['REQUESTS_PER_MINUTE'] = '300'
            print('EXPLICIT LOCAL PREVIEW: SQLite + mock; no real AI acceptance', flush=True)
            task('migrate')
            task('seed')
        if name == 'local':
            task('migrate')
            task('seed')
        port = ENV.get('APP_PORT', ENV.get('PORT', '8000'))
        if name != 'preview-local':
            from dotenv import dotenv_values
            values = dotenv_values(ROOT / '.env')
            port = ENV.get('APP_PORT', ENV.get('PORT', values.get('APP_PORT', values.get('PORT', '8000'))))
        ENV['API_PROXY_TARGET'] = 'http://127.0.0.1:' + str(port)
        processes = [subprocess.Popen([str(PY), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--no-access-log'], cwd=API, env=ENV),
                     subprocess.Popen([PNPM, 'dev', '--host', '127.0.0.1'], cwd=WEB, env=ENV)]
        try:
            print('Web http://localhost:5173 | API http://localhost:' + str(port) + '/docs', flush=True)
            processes[0].wait()
        except KeyboardInterrupt:
            pass
        finally:
            for process in processes:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    process.send_signal(signal.SIGTERM)
    elif name == 'e2e':
        run([PNPM, 'e2e'], WEB)
    elif name in ('eval-mock', 'eval-live'):
        run([PY, ROOT / 'evals/run.py', '--provider', name.split('-')[1]])
    elif name in ('smoke', 'live-smoke'):
        if name == 'live-smoke':
            import sys as _sys
            _sys.path.insert(0,str(API))
            from app.config import settings
            if settings().llm_provider == 'deepseek':
                run([PY, ROOT / 'scripts/deepseek_smoke.py'])
            else:
                run([PY, ROOT / 'scripts/smoke.py','--live'])
        else:
            run([PY, ROOT / 'scripts/smoke.py'])
    elif name == 'ci':
        for item in ('lint', 'typecheck', 'test', 'build', 'e2e', 'eval-mock', 'smoke'):
            task(item)
    else:
        raise SystemExit('Unknown task: ' + name)


if __name__ == '__main__':
    task(sys.argv[1])
