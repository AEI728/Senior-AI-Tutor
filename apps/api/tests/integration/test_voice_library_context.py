from uuid import uuid4
import pytest
from sqlalchemy import select
from app import main
from app.db import Library, Work
from app.auth import local_token


def turn(http, message, rid=None, **context):
    return http.post('/api/v1/agent/turns', json={
        'agent_role': 'companion', 'client_request_id': rid or str(uuid4()),
        'message': message, 'ui_context': {'page': 'home', **context},
    }).json()


@pytest.mark.parametrize('phrase', ['我不想学乐器了', '不再学习音乐', '移除乐器', '删除乐器这个技能'])
def test_negative_learning_removes_only_target_and_keeps_progress(http, phrase):
    http.put('/api/v1/library/music')
    http.put('/api/v1/library/calligraphy')
    http.put('/api/v1/progress/rhythm-basics', json={'position_seconds': 12, 'current_step': 1})
    result = turn(http, phrase)
    assert result['intent'] == 'REMOVE_SKILL' and result['state'] == 'SUCCEEDED'
    assert '乐器' in result['reply']['speech_text']
    assert [r['skill_id'] for r in http.get('/api/v1/library').json()['items']] == ['calligraphy']
    assert http.get('/api/v1/progress/recent').json()['items'][0]['position_seconds'] == 12
    again = turn(http, phrase)
    assert '不在' in again['reply']['speech_text']


def test_ambiguous_removal_clarifies_without_adding(http):
    http.put('/api/v1/library/music')
    result = turn(http, '我不想学这个了')
    assert result['state'] == 'WAITING_USER'
    assert result['pending_clarification']['intent'] == 'REMOVE_SKILL'
    assert result['choices'] == [{'label': '乐器', 'message': '不再学习乐器'}]
    assert turn(http, '乐器')['intent'] == 'REMOVE_SKILL'
    assert http.get('/api/v1/library').json()['items'] == []


def test_dont_remove_and_multiple_targets_do_not_write(http):
    http.put('/api/v1/library/music')
    for message in ['不要移除乐器', '我不想学乐器但想学书法']:
        assert turn(http, message)['state'] == 'WAITING_USER'
        assert [r['skill_id'] for r in http.get('/api/v1/library').json()['items']] == ['music']


def test_music_display_name_is_same_as_ui(http):
    result = turn(http, '我想学乐器')
    assert result['reply']['speech_text'] == '乐器已加入技能库。'
    assert '节奏入门' not in result['reply']['speech_text']


def test_current_shared_example_is_resolved_server_side(http):
    result = turn(http, '我想学这个', page='community', focused_work_id='example-writing')
    assert result['intent'] == 'ADD_SKILL'
    assert [r['skill_id'] for r in http.get('/api/v1/library').json()['items']] == ['calligraphy']
    result = turn(http, '我不想学这个了', page='community', focused_work_id='example-writing')
    assert result['intent'] == 'REMOVE_SKILL'
    assert http.get('/api/v1/library').json()['items'] == []


def test_missing_or_private_work_does_not_use_forged_skill(http, db):
    mine = http.post('/api/v1/community/works', json={
        'title': '学习分享', 'description': '练习记录', 'course_id': 'phone-composition',
        'publish_confirmation': 'SHARE_THIS_WORK',
    }).json()['id']
    assert turn(http, '我想学这个', page='community', focused_work_id=mine)['state'] == 'SUCCEEDED'
    http.headers['Authorization'] = 'Bearer ' + local_token('other-viewer')
    for wid in [mine, 'missing', None]:
        result = turn(http, '我想学这个', page='community', focused_work_id=wid, focused_skill_id='music')
        assert result['state'] == 'WAITING_USER'
        assert http.get('/api/v1/library').json()['items'] == []
    work = db.get(Work, mine)
    work.state = 'APPROVED'
    db.commit()
    result = turn(http, '我想学这个', page='community', focused_work_id=mine)
    assert result['state'] == 'SUCCEEDED'
    assert http.get('/api/v1/library').json()['items'][0]['skill_id'] == 'photography'


def test_real_provider_removal_rule_needs_no_model_and_is_idempotent(http, db, monkeypatch):
    http.put('/api/v1/library/music')
    monkeypatch.setattr(main.cfg, 'llm_provider', 'deepseek')
    def unexpected(*args):
        raise AssertionError('Clear removal should not need an LLM')
    monkeypatch.setattr(main, 'model_plan', unexpected)
    rid = str(uuid4())
    a = turn(http, '我不想学乐器了', rid=rid)
    b = turn(http, '我不想学乐器了', rid=rid)
    assert a['state'] == 'SUCCEEDED' and b['turn_id'] == a['turn_id']
    assert db.scalar(select(Library)) is None
