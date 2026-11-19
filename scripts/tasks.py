"""Cross-platform task runner; records real commands, times and exit codes."""
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'apps/api'
WEB = ROOT / 'apps/web'
PY = API / ('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
PNPM = shutil.which('pnpm.cmd' if os.name == 'nt' else 'pnpm') or 'pnpm'
ENV = dict(os.environ)


def api_port():
    from dotenv import dotenv_values
    values=dotenv_values(ROOT / '.env')
    value=ENV.get('APP_PORT') or ENV.get('PORT') or values.get('APP_PORT') or values.get('PORT') or '8000'
    try:
        port=int(value)
        if not 1 <= port <= 65535:raise ValueError
    except ValueError:
        raise SystemExit('PORT / APP_PORT 必须是1到65535之间的整数。') from None
    return str(port)


def web_command():
    # Local development uses the installed Vite entry directly. No global pnpm required.
    node=shutil.which('node.exe' if os.name=='nt' else 'node')
    vite=WEB/'node_modules/vite/bin/vite.js'
    if not node:raise SystemExit('未找到 Node.js。请安装 Node.js 22或更新版本，然后重新打开 VS Code/终端。')
    if not vite.is_file():raise SystemExit('前端依赖尚未安装。请在 apps/web 执行 pnpm install --frozen-lockfile。')
    return [node,str(vite),'--host','127.0.0.1','--port','5173','--strictPort']


def port_busy(port):
    with socket.socket() as sock:
        sock.settimeout(.5)
        return sock.connect_ex(('127.0.0.1',int(port)))==0


def app_health(port):
    try:
        with urlopen('http://127.0.0.1:'+str(port)+'/health/ready',timeout=2) as response:
            value=json.load(response)
        if value.get('status')=='ok' and 'mock_mode' in value and value.get('database') in ('sqlite','postgresql'):
            return value
    except Exception:
        pass
    return None


def stop_processes(processes):
    # Only stop processes started by this invocation; reused services belong to their original launcher.
    for process in reversed(processes):
        if process.poll() is not None:continue
        if os.name=='nt':
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
        else:
            process.send_signal(signal.SIGTERM)
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill()


def start_local(name):
    port='8000' if name=='preview-local' else api_port()
    frontend=web_command()  # Check all executables before spawning either service.
    backend=[str(PY),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',port,'--no-access-log']
    if not PY.is_file():raise SystemExit('后端虚拟环境不存在，请先在 apps/api 执行 uv sync --frozen。')
    api_running=port_busy(port)
    existing=app_health(port) if api_running else None
    if api_running and not existing:raise SystemExit('后端端口 '+port+' 已被其他进程占用。请先确认占用者，或修改.env里的PORT。')
    if existing and name=='preview-local' and (not existing.get('mock_mode') or existing.get('audio_provider')!='mock'):
        raise SystemExit('该端口运行着真实服务；请先在原终端Ctrl+C停止，再启动模拟模式。')
    web_running=port_busy('5173')
    if web_running and (not existing or app_health('5173')!=existing):
        raise SystemExit('5173端口已有服务，但未确认它连接当前后端。请在原终端Ctrl+C后重新启动。')
    if existing:print('检测到已运行的小伴后端，复用 http://localhost:'+port,flush=True)
    if api_running and web_running:
        print('前后端已在运行，直接打开 http://localhost:5173 ，无需重复启动。',flush=True)
        return
    if name=='preview-local':
        ENV.update(DATABASE_URL='sqlite:///'+(ROOT/'local-preview.db').as_posix(),APP_ENV='local',LLM_PROVIDER='mock',AUDIO_PROVIDER='mock',USE_MOCK_LLM='true',REQUESTS_PER_MINUTE='300')
        print('显式模拟模式：SQLite + mock，不调用真实模型。',flush=True)
    if name in ('local','preview-local') and not api_running:
        task('migrate');task('seed')
    ENV['API_PROXY_TARGET']='http://127.0.0.1:'+port
    processes=[]
    try:
        if not api_running:processes.append(subprocess.Popen(backend,cwd=API,env=ENV))
        if not web_running:processes.append(subprocess.Popen(frontend,cwd=WEB,env=ENV))
        print('网页 http://localhost:5173 | API http://localhost:'+port+'/docs\n保持此终端打开；Ctrl+C停止本次启动的服务。',flush=True)
        while True:
            for process in processes:
                if process.poll() is not None:
                    raise SystemExit('服务已停止，退出码 '+str(process.returncode)+'。本次启动的其他服务已清理。')
            time.sleep(.25)
    except KeyboardInterrupt:
        pass
    except OSError:
        raise SystemExit('启动服务失败，请检查 Node.js、Python环境及端口。本次启动的进程已清理。') from None
    finally:
        stop_processes(processes)


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
    folder = ROOT / 'artifacts'
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
            test_db=ROOT/'artifacts/databases/api-test.db'
            test_db.parent.mkdir(parents=True,exist_ok=True)
            env['DATABASE_URL'] = 'sqlite:///' + test_db.as_posix()
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
        run([PY, ROOT / 'scripts/check_agent_skills.py'])
        run([PY, ROOT / 'scripts/export_contract.py', '--check'])
        run([PNPM, 'exec', 'openapi-typescript', '../../docs/api/openapi.snapshot.json', '--check', '-o', 'src/generated/api.d.ts'], WEB)
    elif name == 'api-dev':
        python('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', api_port())
    elif name == 'web-dev':
        ENV['API_PROXY_TARGET']='http://127.0.0.1:'+api_port()
        run(web_command(), WEB)
    elif name in ('dev', 'local', 'preview-local'):
        start_local(name)
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
        for item in ('lint', 'typecheck', 'test', 'contract', 'build', 'e2e', 'eval-mock', 'smoke'):
            task(item)
    else:
        raise SystemExit('Unknown task: ' + name)


if __name__ == '__main__':
    task(sys.argv[1])
