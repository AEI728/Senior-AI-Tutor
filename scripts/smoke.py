import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4
import httpx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'apps/api'))
from app.config import settings  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--live', action='store_true')
args = parser.parse_args()
cfg = settings()
if args.live and (cfg.llm_provider != 'openai' or cfg.audio_provider != 'openai' or not cfg.openai_api_key):
    raise SystemExit('BLOCKED_EXTERNAL_DEPENDENCY: real providers and OPENAI_API_KEY required')

with httpx.Client(base_url=os.environ.get('API_URL', 'http://127.0.0.1:8000'), timeout=30) as c:
    health = c.get('/health/ready');health.raise_for_status()
    if args.live and (health.json()['mock_mode'] or health.json()['audio_provider'] != 'openai'):
        raise SystemExit('BLOCKED: running server is not using real providers')
    auth = c.post('/api/v1/dev/session');auth.raise_for_status()
    c.headers['Authorization'] = 'Bearer ' + auth.json()['access_token']
    catalog = c.get('/api/v1/catalog/skills');catalog.raise_for_status()
    assert catalog.json()['items'][0]['id'] == 'home-gardening'
    before = c.get('/api/v1/library').json()
    def turn(message, request_id=None):
        r = c.post('/api/v1/agent/turns', json={'agent_role': 'companion', 'message': message,
            'client_request_id': request_id or str(uuid4()), 'ui_context': {'page': 'home'}})
        r.raise_for_status()
        return r.json()
    browse = turn('我想看看园艺课')
    assert browse['intent'] == 'DISCOVER_SKILL'
    assert before == c.get('/api/v1/library').json()
    rid = str(uuid4())
    joined = turn('我想学园艺', rid)
    assert joined['state'] == 'SUCCEEDED' and joined['intent'] == 'ADD_SKILL'
    assert turn('我想学园艺', rid)['turn_id'] == joined['turn_id']
    session = c.post('/api/v1/practice/sessions', json={'course_id': 'repotting-basics'})
    session.raise_for_status()
    if args.live:
        fixture = os.environ.get('LIVE_AUDIO_FILE', '')
        if not fixture or not Path(fixture).is_file():
            raise SystemExit('BLOCKED: provide licensed LIVE_AUDIO_FILE (<=20s WAV, 我想学养花)')
        with open(fixture, 'rb') as f:
            audio = c.post('/api/v1/audio/transcriptions', files={'file': ('fixture.wav', f, 'audio/wav')})
        audio.raise_for_status()
        assert audio.json()['provider'] == 'openai' and audio.json()['text'].strip()
        spoken = c.post('/api/v1/audio/speech', json={'reply_id': joined['reply']['id']})
        spoken.raise_for_status()
        import io
        from mutagen.mp3 import MP3
        assert spoken.headers['content-type'] == 'audio/mpeg' and MP3(io.BytesIO(spoken.content)).info.length > 0
    print('PASS:', 'REAL Responses + ASR + TTS' if args.live else 'LOCAL catalog + browse + join + replay + practice',
          '| provider=', health.json()['provider'], '| db=', health.json()['database'])
