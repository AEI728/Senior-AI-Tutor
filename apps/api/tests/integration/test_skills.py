from uuid import uuid4
import pytest
from sqlalchemy import select
from app import agent, main
from app.db import Course, Library, Operation
from app.schemas import Plan
from app.skill_runtime import compose_prompt, validate_plan


def turn(http, message, **context):
    return http.post('/api/v1/agent/turns', json={
        'agent_role': 'companion', 'client_request_id': str(uuid4()),
        'message': message, 'ui_context': {'page': 'home', **context},
    }).json()


def test_real_model_adapter_uses_packaged_instructions(http, db, monkeypatch):
    # Exercise the production adapter, replacing only the external HTTP call.
    monkeypatch.setattr(main.cfg, 'llm_provider', 'deepseek')
    seen = {}

    def model(schema, prompt, data):
        seen.update(prompt=prompt, data=data)
        return Plan(intent='ADD_SKILL', skill_id='photography', course_id=None), 'provider-test-id'

    monkeypatch.setattr(agent, 'structured', model)
    result = turn(http, '我想学摄影')
    assert result['state'] == 'SUCCEEDED'
    assert 'Skill 01' in seen['prompt'] and '小伴共享 System Prompt' in seen['prompt']
    assert 'Skill 02' not in seen['prompt']  # unrelated skill is not dumped into every request
    assert len(seen['data']['available_courses']) == 12
    assert {s['id'] for s in seen['data']['available_catalog']} == {'home-gardening', 'photography', 'calligraphy', 'music'}
    assert set(result['skill_trace']) == {'intent-recognition', 'operation-execution', 'response-generation'}
    operation = db.scalar(select(Operation).where(Operation.tool_name == 'model.call'))
    assert operation.state == 'SUCCEEDED'


def test_recommend_is_read_only_and_selection_opens_real_course(http):
    result = turn(http, '推荐一门摄影课程')
    recommendations = result['recommendations']
    assert 1 <= len(recommendations) <= 2
    assert all(r['skill_id'] == 'photography' for r in recommendations)
    assert result['ui_actions'] == []
    assert http.get('/api/v1/library').json()['items'] == []
    assert 'course-recommendation' in result['skill_trace']
    chosen = turn(http, '打开第一门')
    assert chosen['ui_actions'][0]['payload']['course_id'] == recommendations[0]['course_id']
    assert http.get('/api/v1/library').json()['items'] == []


def test_recommend_missing_metadata_never_fabricates(http):
    result = turn(http, '推荐一门简单的摄影课程，10分钟以内')
    assert result['recommendations'] == []
    assert 'duration_seconds' in result['missing_conditions']
    assert result['ui_actions'] == []


def test_recommend_hard_filters_use_actual_course_fields(http, db):
    c = db.get(Course, 'phone-composition')
    c.data = {**c.data, 'duration_seconds': 300, 'difficulty': 'beginner'}
    db.commit()
    result = turn(http, '推荐简单的摄影课，10分钟以内')
    assert [r['course_id'] for r in result['recommendations']] == ['phone-composition']
    assert {'BEGINNER', 'DURATION_MATCH'} <= set(result['recommendations'][0]['reason_codes'])


def test_two_failures_stop_followup_then_new_request_resets(http):
    one = turn(http, '这个我想学')
    two = turn(http, '这个我想学')
    assert one['recovery']['strategy'] == 'clarify'
    assert two['recovery']['strategy'] == 'manual_fallback'
    assert two['recovery']['stop_voice_followups'] is True
    assert '?' not in two['reply']['speech_text'] and '？' not in two['reply']['speech_text']
    assert len(two['choices']) <= 2 and two['ui_actions'] == []
    assert turn(http, '我想学书法')['state'] == 'SUCCEEDED'


def test_correction_requires_confirmation_and_preserves_progress(http):
    turn(http, '我想学书法')
    http.put('/api/v1/progress/calligraphy-lines', json={'position_seconds': 30, 'current_step': 1})
    correction = turn(http, '不是这个，我想学摄影')
    assert correction['recovery']['strategy'] == 'confirm_correction'
    assert [r['skill_id'] for r in http.get('/api/v1/library').json()['items']] == ['calligraphy']
    assert turn(http, '确认')['state'] == 'SUCCEEDED'
    assert [r['skill_id'] for r in http.get('/api/v1/library').json()['items']] == ['photography']
    assert http.get('/api/v1/progress/recent').json()['items'][0]['position_seconds'] == 30


def test_stale_correction_cannot_remove_rejoined_membership(http):
    turn(http, '我想学书法')
    turn(http, '不是这个，我想学摄影')
    http.delete('/api/v1/library/calligraphy')
    http.put('/api/v1/library/calligraphy')
    result = turn(http, '确认')
    assert result['state'] == 'WAITING_USER'
    assert [r['skill_id'] for r in http.get('/api/v1/library').json()['items']] == ['calligraphy']


def test_stop_invalidates_pending_ui_action(http):
    opening = turn(http, '打开技能广场')
    aid = opening['ui_actions'][0]['id']
    assert turn(http, '停')['recovery']['strategy'] == 'stop'
    late = http.post('/api/v1/agent/ui-actions/'+aid+'/ack', json={'result': 'applied'}).json()
    assert late['state'] == 'FAILED' and late['ui_actions'] == []


def test_navigation_and_practice_do_not_depend_on_test_course(http, db, monkeypatch):
    monkeypatch.setattr(main.cfg, 'app_env', 'production')
    result = turn(http, '打开技能广场')
    assert result['ui_actions'][0]['payload']['page'] == 'skills'
    practice = turn(http, '打开陪练')
    assert practice['ui_actions'][0]['type'] == 'OPEN_PAGE'
    assert practice['ui_actions'][0]['payload']['page'] == 'practice'


def test_skill_switch_does_not_reuse_previous_course_and_partial_says_real_name(http):
    result = turn(http, '把书法加入，再打开第一课', course_id='repotting-basics')
    assert result['ui_actions'][0]['payload']['course_id'] == 'calligraphy-lines'
    failed = http.post('/api/v1/agent/ui-actions/'+result['ui_actions'][0]['id']+'/ack', json={'result': 'failed'}).json()
    assert failed['state'] == 'PARTIAL'
    assert '书法' in failed['reply']['speech_text'] and '园艺' not in failed['reply']['speech_text']


def test_fabricated_course_from_model_is_blocked_before_write(http, db, monkeypatch):
    monkeypatch.setattr(main.cfg, 'llm_provider', 'deepseek')
    monkeypatch.setattr(main, 'model_plan', lambda *args: (
        Plan(intent='ADD_SKILL_AND_OPEN_LESSON', skill_id='photography', course_id='invented-course'), 'x',
    ))
    result = turn(http, '学摄影然后打开一节课')
    assert result['state'] == 'FAILED' and result['ui_actions'] == []
    assert db.scalar(select(Library)) is None


def test_role_prompts_and_invalid_business_ids():
    prompt = compose_prompt('response-generation', extra='仅语音，无摄像头')
    assert 'Skill 04' in prompt and '小伴共享 System Prompt' in prompt
    with pytest.raises(ValueError, match='SKILL_NOT_FOUND'):
        validate_plan(Plan(intent='ADD_SKILL', skill_id='photography', course_id=None), [])


def test_manifest_is_authenticated(http):
    data = http.get('/api/v1/agent/skills').json()
    assert len(data['skills']) == 5
    assert all(s['version'] == '1.1.0' and len(s['sha256']) == 64 for s in data['skills'])
    http.headers.pop('Authorization')
    assert http.get('/api/v1/agent/skills').status_code == 401


def test_execution_policy_removal_prevents_database_write(http, db, monkeypatch):
    from app import skill_runtime

    original = skill_runtime.load_skill
    def limited(name):
        skill = original(name)
        if name == 'operation-execution':
            skill['policy']['intent_tools']['ADD_SKILL'] = []
        return skill
    monkeypatch.setattr(skill_runtime, 'load_skill', limited)
    result = turn(http, '我想学摄影')
    assert result['state'] == 'FAILED'
    assert db.scalar(select(Library)) is None


def test_provider_retry_is_bounded_and_does_not_retry_auth(monkeypatch):
    import httpx
    from app.providers import retry, ProviderError

    calls = []
    def unavailable():
        calls.append(1)
        raise httpx.ConnectError('offline')
    with pytest.raises(ProviderError):
        retry(unavailable)
    assert len(calls) == 2
    calls.clear()
    def unauthorized():
        calls.append(1)
        request = httpx.Request('POST', 'https://test.invalid')
        raise httpx.HTTPStatusError('auth', request=request, response=httpx.Response(401, request=request))
    with pytest.raises(ProviderError):
        retry(unauthorized)
    assert len(calls) == 1
