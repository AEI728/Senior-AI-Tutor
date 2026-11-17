"""Small real-provider acceptance using an isolated internal-test account."""
import io
import json
import secrets
import sys
import time
import wave
from pathlib import Path
from uuid import uuid4
import httpx

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'apps/api'))
from app.config import settings  # noqa: E402
from app.providers import audio_request, normalize_wav  # noqa: E402

cfg=settings()
if cfg.llm_provider!='deepseek' or cfg.audio_provider!='deepseek':raise SystemExit('Real DeepSeek providers required')
result={'provider':'deepseek','model':cfg.deepseek_model,'started_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
started=time.monotonic()
try:
    with httpx.Client(base_url='http://127.0.0.1:'+str(cfg.app_port),timeout=65) as c:
        health=c.get('/health/ready');health.raise_for_status();assert health.json()['provider']=='deepseek' and not health.json()['mock_mode']
        auth=c.post('/api/v1/auth/register',json={'username':'audit_'+uuid4().hex[:12],'password':secrets.token_urlsafe(28)});auth.raise_for_status()
        c.headers['Authorization']='Bearer '+auth.json()['access_token']
        fixture=normalize_wav(audio_request('tts',json={'text':'我想学养花。','voice_id':cfg.deepseek_tts_voice,'format':'wav'}).content)
        with wave.open(io.BytesIO(fixture)) as w:result['fixture_seconds']=round(w.getnframes()/w.getframerate(),2)
        assert result['fixture_seconds']<20
        transcription=c.post('/api/v1/audio/transcriptions',files={'file':('original-fixture.wav',fixture,'audio/wav')});transcription.raise_for_status()
        transcript=transcription.json()['text'];assert any(s in transcript for s in ('养花','园艺'))
        result['asr']='PASS'
        rid=str(uuid4());body={'agent_role':'companion','client_request_id':rid,'message':transcript,'ui_context':{'page':'home'}}
        response=c.post('/api/v1/agent/turns',json=body);response.raise_for_status();turn=response.json()
        assert turn['intent']=='ADD_SKILL' and turn['state']=='SUCCEEDED',turn.get('error_code')
        assert len(c.get('/api/v1/library').json()['items'])==1
        assert c.post('/api/v1/agent/turns',json=body).json()['turn_id']==turn['turn_id']
        result['model_tool_database_replay']='PASS'
        speech=c.post('/api/v1/audio/speech',json={'reply_id':turn['reply']['id']});speech.raise_for_status()
        with wave.open(io.BytesIO(speech.content)) as w:assert 0<w.getnframes()/w.getframerate()<60
        result['owned_reply_tts']='PASS'
        browse=c.post('/api/v1/agent/turns',json={'agent_role':'companion','client_request_id':str(uuid4()),'message':'看看摄影课程','ui_context':{'page':'home'}}).json()
        assert browse['intent']=='DISCOVER_SKILL' and browse['ui_actions'][0]['type']=='OPEN_PAGE'
        assert len(c.get('/api/v1/library').json()['items'])==1
        result['browse_no_join']='PASS'
        # API-only run deliberately does not fabricate a browser navigation ACK.
        result['browser_navigation']='NOT_RUN_IN_THIS_SCRIPT'
        c.request('DELETE','/api/v1/me/data',json={'confirmation':'DELETE_MY_DATA'}).raise_for_status()
        result['status']='PASS'
except Exception as e:
    result['status']='FAIL';result['error_code']=getattr(e,'code',type(e).__name__)
result['duration_seconds']=round(time.monotonic()-started,2)
(root/'docs/evals/deepseek-end-to-end-2026-11-16.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(result,ensure_ascii=False))
raise SystemExit(0 if result['status']=='PASS' else 1)
