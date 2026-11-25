import io
import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
from sqlalchemy import select, delete, text, func, case
from sqlalchemy.exc import IntegrityError
from mutagen import File as MediaFile
from .config import settings
from .db import (
    database,
    engine,
    User,
    Skill,
    Course,
    Library,
    CompletedSkill,
    Progress,
    Practice,
    StepEvent,
    Turn,
    Operation,
    Action,
    Reply,
    Event,
    Work,
    WorkMedia,
    WorkVideo,
    FeedReaction,
    FeedComment,
    Account,
    now,
)
from .auth import current_user, local_token
from .schemas import (
    TurnInput,
    ProgressInput,
    PracticeInput,
    Command,
    Ack,
    Speech,
    DeleteData,
    Telemetry,
    CourseDetail,
)
from .agent import mock_plan, model_plan, tutor_answer, request_hash, client, Budget, companion_answer, learning_rule
from .providers import ProviderError, audio_request, structured, normalize_wav
from .schemas import Plan, TutorDecision
from .skill_runtime import (
    manifest, mark_skill, template, validate_plan, course_candidates, recommend_courses,
    confirmed_recovery, recover, correction_turn, undo_operation, undo_addition,
    cancel_pending, partial_text, compose_prompt, require_tool, resolve_page_context,
)

cfg = settings()
app = FastAPI(title="小伴 · 银发 AI 私教", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[cfg.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
)
rates: dict[str, deque] = defaultdict(deque)
logger = logging.getLogger("xiaoban")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


@app.middleware("http")
async def audit(request: Request, call_next):
    request.state.request_id = str(uuid4())
    started = time.monotonic()
    # Per-identity request limits; production additionally requires reverse-proxy limits.
    identity = request.headers.get("authorization", request.client.host if request.client else "local")
    import hashlib

    key = hashlib.sha256(identity.encode()).hexdigest()
    bucket = rates[key]
    t = time.monotonic()
    while bucket and t - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= cfg.requests_per_minute:
        return JSONResponse(
            {
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "操作较频繁，请稍后再试。",
                    "retryable": True,
                    "request_id": request.state.request_id,
                }
            },
            status_code=429,
        )
    bucket.append(t)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(
        json.dumps(
            {
                "request_id": request.state.request_id,
                "user_pseudonym": getattr(request.state, "user_pseudonym", None),
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return JSONResponse(
        {
            "error": {
                "code": str(error.detail),
                "message": "操作未完成，请检查后重试或使用页面按钮。",
                "retryable": error.status_code in (429, 503),
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
        status_code=error.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse(
        {
            "error": {
                "code": "INVALID_INPUT",
                "message": "输入格式不正确，请检查。",
                "retryable": False,
                "request_id": request.state.request_id,
            }
        },
        status_code=422,
    )


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "DATABASE_UNAVAILABLE") from None
    return {
        "status": "ok",
        "db": "ok",
        "model": "mock" if cfg.llm_provider == "mock" else "configured_not_verified",
        "provider": cfg.llm_provider,
        "audio_provider": cfg.audio_provider,
        "mock_mode": cfg.llm_provider == "mock",
        "model_name": cfg.deepseek_model if cfg.llm_provider == "deepseek" else cfg.openai_model,
        "database": engine.dialect.name,
        "can_see_video": False,
    }


@app.post("/api/v1/dev/session")
def login(db=Depends(database)):
    if cfg.app_env not in ("local", "test") or cfg.auth_mode != "dev":
        raise HTTPException(404, "NOT_FOUND")
    user = db.scalar(select(User).where(User.auth_subject == "xiaoban-local:demo-user"))
    if not user:
        user = User(auth_subject="xiaoban-local:demo-user")
        db.add(user)
        db.flush()
    return {"access_token": local_token(), "token_type": "bearer", "user_id": user.id}


@app.get("/api/v1/me")
def me(user=Depends(current_user), db=Depends(database)):
    account = db.scalar(select(Account).where(Account.user_id == user.id))
    return {
        "id": user.id,
        "locale": "zh-CN",
        "speech_rate": 1,
        "proactive_greeting": False,
        "provider": cfg.llm_provider,
        "audio_provider": cfg.audio_provider,
        "auth_mode": cfg.auth_mode,
        "database": engine.dialect.name,
        "is_admin": bool(account and account.is_admin) or user.auth_subject in cfg.admin_subjects.split(","),
    }


def course_or_404(db, course_id):
    course = db.get(Course, course_id)
    if not course or (
        cfg.app_env not in ("local", "test") and course.data.get("review_status") != "approved"
    ):
        raise HTTPException(404, "COURSE_NOT_FOUND")
    return course


def practice_or_404(db, user, session_id):
    session = db.scalar(
        select(Practice).where(Practice.id == session_id, Practice.user_id == user.id).with_for_update()
    )
    if not session:
        raise HTTPException(404, "SESSION_NOT_FOUND")
    return session


@app.get("/api/v1/catalog/skills")
def catalog(query: str = "", user=Depends(current_user), db=Depends(database)):
    items = db.scalars(select(Skill)).all()
    return {
        "items": [
            {"id": s.id, "name": s.name, "joined": bool(db.get(Library, (user.id, s.id)))}
            for s in items
            if (not query or query in s.name or query in ("养花", "盆栽"))
            and (
                cfg.app_env in ("local", "test")
                or any(
                    c.data.get("review_status") == "approved"
                    for c in db.scalars(select(Course).where(Course.skill_id == s.id))
                )
            )
        ]
    }


@app.get("/api/v1/catalog/skills/{skill_id}/courses")
def courses(skill_id: str, user=Depends(current_user), db=Depends(database)):
    if not db.get(Skill, skill_id):
        raise HTTPException(404, "SKILL_NOT_FOUND")
    return {
        "items": [
            c.data
            for c in db.scalars(
                select(Course)
                .where(Course.skill_id == skill_id)
                .order_by(
                    case(
                        (
                            Course.id.in_(
                                [
                                    "repotting-basics",
                                    "calligraphy-lines",
                                    "phone-composition",
                                    "rhythm-basics",
                                ]
                            ),
                            0,
                        ),
                        else_=1,
                    ),
                    Course.id,
                )
            )
            if cfg.app_env in ("local", "test") or c.data.get("review_status") == "approved"
        ]
    }


@app.get("/api/v1/catalog/courses/{course_id}", response_model=CourseDetail)
def course_detail(course_id: str, user=Depends(current_user), db=Depends(database)):
    c = course_or_404(db, course_id)
    return {**c.data, "skill_id": c.skill_id, "media_url": c.data["media_path"]}


@app.get("/api/v1/catalog/courses/{course_id}/demo-video")
def demo_video(course_id: str, user=Depends(current_user), db=Depends(database)):
    course_or_404(db, course_id)
    from .config import ROOT

    folder = (ROOT / "media").resolve()
    path = (folder / (course_id + ".mp4")).resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise HTTPException(404, "VIDEO_NOT_FOUND")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/v1/library")
def library(user=Depends(current_user), db=Depends(database)):
    return {
        "items": [
            {"skill_id": r.skill_id, "joined_at": r.joined_at, "name": db.get(Skill, r.skill_id).name}
            for r in db.scalars(select(Library).where(Library.user_id == user.id))
        ]
    }


def add_skill(db, user, skill_id):
    if not db.get(Skill, skill_id):
        raise HTTPException(404, "SKILL_NOT_FOUND")
    db.execute(delete(CompletedSkill).where(CompletedSkill.user_id == user.id, CompletedSkill.skill_id == skill_id))
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    result = db.execute(
        insert(Library)
        .values(user_id=user.id, skill_id=skill_id, joined_at=now())
        .on_conflict_do_nothing(index_elements=["user_id", "skill_id"])
    )
    return {"skill_id": skill_id, "status": "added" if result.rowcount else "already_joined"}


@app.put("/api/v1/library/{skill_id}")
def join(skill_id: str, user=Depends(current_user), db=Depends(database)):
    return add_skill(db, user, skill_id)


@app.delete("/api/v1/library/{skill_id}")
def remove(skill_id: str, user=Depends(current_user), db=Depends(database)):
    return remove_skill(db, user, skill_id)


def remove_skill(db, user, skill_id):
    r = db.execute(delete(Library).where(Library.user_id == user.id, Library.skill_id == skill_id))
    return {"skill_id": skill_id, "status": "removed" if r.rowcount else "not_joined"}


@app.get("/api/v1/library/completed")
def completed_skills(user=Depends(current_user), db=Depends(database)):
    return {"items": [{"skill_id": r.skill_id, "completed_at": r.completed_at}
                      for r in db.scalars(select(CompletedSkill).where(CompletedSkill.user_id == user.id))]}


@app.post("/api/v1/library/{skill_id}/complete")
def complete_skill(skill_id: str, user=Depends(current_user), db=Depends(database)):
    if db.get(CompletedSkill, (user.id, skill_id)):
        return {"skill_id": skill_id, "status": "already_completed"}
    joined = db.get(Library, (user.id, skill_id))
    if not joined:
        raise HTTPException(404, "SKILL_NOT_JOINED")
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(CompletedSkill).values(user_id=user.id, skill_id=skill_id, completed_at=now())
               .on_conflict_do_nothing(index_elements=["user_id", "skill_id"]))
    db.execute(delete(Library).where(Library.user_id == user.id, Library.skill_id == skill_id))
    return {"skill_id": skill_id, "status": "completed"}


@app.get("/api/v1/progress/recent")
def recent(user=Depends(current_user), db=Depends(database)):
    return {
        "items": [
            {
                "course_id": p.course_id,
                "position_seconds": p.position_seconds,
                "current_step": p.current_step,
                "updated_at": p.updated_at,
            }
            for p in db.scalars(
                select(Progress).where(Progress.user_id == user.id).order_by(Progress.updated_at.desc())
            )
        ]
    }


def save_progress(db, user, course_id, position_seconds, current_step):
    course = course_or_404(db, course_id)
    if current_step > len(course.data["steps"]):
        raise HTTPException(422, "STEP_OUT_OF_RANGE")
    p = db.get(Progress, (user.id, course_id))
    if not p:
        p = Progress(user_id=user.id, course_id=course_id)
        db.add(p)
    p.position_seconds, p.current_step, p.updated_at = position_seconds, current_step, now()
    return {"course_id": course_id, "position_seconds": position_seconds, "current_step": current_step}


@app.put("/api/v1/progress/{course_id}")
def progress(course_id: str, body: ProgressInput, user=Depends(current_user), db=Depends(database)):
    return save_progress(db, user, course_id, body.position_seconds, body.current_step)


def session_json(db, s):
    c = course_or_404(db, s.course_id)
    return {
        "id": s.id,
        "course_id": s.course_id,
        "state": s.state,
        "current_step": s.current_step,
        "step": c.data["steps"][s.current_step - 1],
        "total_steps": len(c.data["steps"]),
        "quality_verified": False,
        "can_see_video": False,
        "completed_steps": [
            e.step_no for e in db.scalars(select(StepEvent).where(StepEvent.session_id == s.id))
        ],
    }


def create_practice(db, user, course_id):
    course_or_404(db, course_id)
    p = db.get(Progress, (user.id, course_id))
    s = Practice(user_id=user.id, course_id=course_id, current_step=p.current_step if p else 1)
    db.add(s)
    db.flush()
    return s


@app.post("/api/v1/practice/sessions", status_code=201)
def new_practice(body: PracticeInput, user=Depends(current_user), db=Depends(database)):
    return session_json(db, create_practice(db, user, body.course_id))


@app.get("/api/v1/practice/sessions/{sid}")
def get_practice(sid: str, user=Depends(current_user), db=Depends(database)):
    return session_json(db, practice_or_404(db, user, sid))


@app.post("/api/v1/practice/sessions/{sid}/commands")
def command(sid: str, body: Command, user=Depends(current_user), db=Depends(database)):
    s = practice_or_404(db, user, sid)
    transitions = {
        "START": {"READY": "ACTIVE", "ACTIVE": "ACTIVE"},
        "RESUME": {"PAUSED": "ACTIVE"},
        "PAUSE": {"ACTIVE": "PAUSED", "READY": "PAUSED", "PAUSED": "PAUSED"},
        "STOP": {"READY": "ABANDONED", "ACTIVE": "ABANDONED", "PAUSED": "ABANDONED"},
    }
    if s.state not in transitions[body.command]:
        raise HTTPException(409, "INVALID_SESSION_TRANSITION")
    s.state = transitions[body.command][s.state]
    s.updated_at = now()
    return session_json(db, s)


def response_for(db, user, turn, text_value, intent, state="SUCCEEDED", actions=None, completed=None):
    mark_skill(turn, "response-generation")
    trace = turn.response.get("skill_trace", {})
    for operation in db.scalars(select(Operation).where(
        Operation.turn_id == turn.id, Operation.tool_name == "model.call", Operation.state == "RUNNING",
    )):
        operation.state = "SUCCEEDED"
        operation.result = {**operation.result, "skill_trace": trace}
    reply = Reply(user_id=user.id, turn_id=turn.id, text=text_value)
    db.add(reply)
    db.flush()
    turn.state = state
    turn.response = {
        "turn_id": turn.id,
        "state": state,
        "intent": intent,
        "reply": {"id": reply.id, "display_text": text_value, "speech_text": text_value},
        "ui_actions": actions or [],
        "completed_steps": completed or [],
        "needs_clarification": state == "WAITING_USER",
        "choices": [],
        "fallback_actions": ["OPEN_SKILLS", "OPEN_RECENT"] if state == "WAITING_USER" else [],
        "provider": cfg.llm_provider,
        "mock_mode": cfg.llm_provider == "mock",
        "skill_trace": trace,
        "system_prompt_sha256": manifest()["system_prompt_sha256"],
    }
    return turn.response


@app.get("/api/v1/agent/skills")
def agent_skills(user=Depends(current_user)):
    return manifest()


def reserve_model(db, user, turn):
    if cfg.llm_provider == "mock":
        return
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    used = db.scalar(
        select(func.count())
        .select_from(Operation)
        .where(
            Operation.user_id == user.id,
            Operation.tool_name == "model.call",
            Operation.created_at >= now()[:10],
        )
    )
    if used >= cfg.model_calls_per_day:
        raise HTTPException(429, "DAILY_MODEL_BUDGET_EXCEEDED")
    db.add(
        Operation(
            turn_id=turn.id,
            user_id=user.id,
            idempotency_key=turn.id + ":model",
            tool_name="model.call",
            state="RUNNING",
            result={
                "model": cfg.deepseek_model if cfg.llm_provider == "deepseek" else cfg.openai_model,
                "provider": cfg.llm_provider,
            },
        )
    )
    db.flush()


def tutor_turn(db, user, turn, body):
    if not body.practice_session_id or body.ui_context.page != "practice":
        raise HTTPException(422, "TUTOR_CONTEXT_REQUIRED")
    s = practice_or_404(db, user, body.practice_session_id)
    c = course_or_404(db, s.course_id).data
    m = body.message.strip()
    semantic_action = None
    # Non-template controls use a structured model decision, never a free-form state write.
    if cfg.llm_provider == "deepseek" and not any(
        x in m
        for x in (
            "胸痛",
            "呼吸困难",
            "头晕",
            "不舒服",
            "退出",
            "等等",
            "停",
            "别说了",
            "慢",
            "继续",
            "再讲",
            "重复",
            "下一步",
            "我完成了",
            "做好了",
        )
    ):
        reserve_model(db, user, turn)
        decision, _ = structured(
            TutorDecision,
            compose_prompt(extra="当前角色为课程陪练控制，输出TutorDecision。只记录明确、与当前步骤相关的自述完成；疑问或猜测不算完成。ANSWER是普通提问，STOP表示退出。"),
            {"message": m, "current_step": c["steps"][s.current_step - 1], "session_state": s.state},
        )
        semantic_action = decision.action
        replacement = {
            "COMPLETE": "我完成了",
            "PAUSE": "等等",
            "RESUME": "继续",
            "REPEAT": "再讲一次",
            "STOP": "退出",
            "SLOW": "说慢一点",
        }
        if decision.action == "CLARIFY":
            return response_for(
                db, user, turn, "您是在说当前这一步已经完成了吗？确认后我再记录。", "TUTOR", "WAITING_USER"
            )
        m = replacement.get(decision.action, m)
    if any(x in m for x in ("胸痛", "呼吸困难", "意识异常", "严重出血")):
        s.state = "PAUSED"
        reply = "请立即停止练习，请身边的人协助联系当地急救服务。不要继续操作。"
    elif any(x in m for x in ("头晕", "不舒服")):
        s.state = "PAUSED"
        reply = "先停下来休息，放稳工具。如不适持续或加重，请向身边的人或医疗人员求助。"
    elif "退出" in m:
        s.state = "ABANDONED"
        reply = "本次陪练已结束，自述进度已保存。可以返回课程。"
    elif s.state in ("COMPLETED", "ABANDONED"):
        reply = "本次陪练已结束，您可以回到课程重新开始。"
    elif any(x in m for x in ("等等", "停", "别说了")):
        s.state = "PAUSED"
        reply = "已暂停。准备好时说“继续”。"
    elif "慢" in m:
        reply = "好的，本次播放可以使用慢速，不会改动长期偏好。"
    elif "继续" == m:
        s.state = "ACTIVE"
        reply = c["steps"][s.current_step - 1]["instruction"]
    elif any(x in m for x in ("再讲", "重复", "下一步")) and "完成" not in m and "已经" not in m:
        reply = (
            "当前步骤：" + c["steps"][s.current_step - 1]["instruction"] + " 做完后请告诉我，不会自动跳步。"
        )
    elif (
        semantic_action in (None, "COMPLETE")
        and any(x in m for x in ("我完成了", "我已经", "做好了", "准备好了"))
        and not any(x in m for x in ("吗", "吧", "应该", "?", "？"))
    ):
        if s.state != "ACTIVE":
            reply = "当前处于暂停状态，请先说“继续”，再记录完成。"
        else:
            step_no = s.current_step
            if not db.scalar(
                select(StepEvent).where(StepEvent.session_id == s.id, StepEvent.step_no == step_no)
            ):
                db.add(StepEvent(session_id=s.id, step_no=step_no))
            if s.current_step < len(c["steps"]):
                s.current_step += 1
                reply = "已记录您自述完成。接下来：" + c["steps"][s.current_step - 1]["instruction"]
            else:
                s.state = "COMPLETED"
                reply = "已记录您自述完成全部步骤。这是自述进度，尚未核验动作质量。"
            save_progress(db, user, s.course_id, 0, s.current_step)
            db.add(
                Operation(
                    turn_id=turn.id,
                    user_id=user.id,
                    tool_name="record_user_step",
                    idempotency_key=turn.id + ":step",
                    state="SUCCEEDED",
                    result={
                        "step_no": step_no,
                        "completion_source": "user_reported",
                        "quality_verified": False,
                    },
                )
            )
    else:
        if not db.scalar(
            select(Operation).where(Operation.turn_id == turn.id, Operation.tool_name == "model.call")
        ):
            reserve_model(db, user, turn)
        reply = tutor_answer(m, c, c["steps"][s.current_step - 1])
    s.updated_at = now()
    result = response_for(db, user, turn, reply, "TUTOR")
    result["practice"] = session_json(db, s)
    # Reassign JSON after mutation for SQLAlchemy change tracking.
    turn.response = dict(result)
    return result


@app.post("/api/v1/agent/turns")
def agent_turn(body: TurnInput, user=Depends(current_user), db=Depends(database)):
    fingerprint = request_hash(body.model_dump(mode="json"))
    old = db.scalar(
        select(Turn).where(Turn.user_id == user.id, Turn.client_request_id == str(body.client_request_id))
    )
    if old:
        if old.request_hash != fingerprint:
            raise HTTPException(409, "IDEMPOTENCY_KEY_REUSED")
        expire_actions(db, old)
        return JSONResponse(old.response, status_code=202 if old.state == "WAITING_UI_ACK" else 200)
    if body.agent_role == "companion" and body.practice_session_id:
        raise HTTPException(422, "COMPANION_NOT_ALLOWED_IN_PRACTICE")
    turn = Turn(
        user_id=user.id,
        agent_role=body.agent_role,
        client_request_id=str(body.client_request_id),
        request_hash=fingerprint,
    )
    try:
        with db.begin_nested():
            db.add(turn)
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "REQUEST_IN_PROGRESS_RETRY_SAME_ID") from None
    completed = []
    try:
        if body.agent_role == "tutor":
            result = tutor_turn(db, user, turn, body)
        else:
            if any(x in body.message for x in ("胸痛", "呼吸困难", "意识异常", "严重出血")):
                return response_for(
                    db, user, turn, "请立即停止操作，请身边的人协助联系当地急救服务。", "SAFETY"
                )
            mark_skill(turn, "intent-recognition")
            pending_turn = db.scalar(
                select(Turn)
                .where(Turn.user_id == user.id, Turn.agent_role == "companion", Turn.id != turn.id)
                .order_by(Turn.created_at.desc())
                .limit(1)
            )
            pending = (
                pending_turn.response.get("pending_clarification", {})
                if pending_turn and pending_turn.state == "WAITING_USER"
                else {}
            )
            available = [{"id": s.id, "name": s.name} for s in db.scalars(select(Skill))]
            actual_courses = course_candidates(db)
            context, page_content = resolve_page_context(db, user, body.ui_context)
            corrected = correction_turn(db, user, turn, body.message, pending)
            if corrected:
                return corrected
            plan = learning_rule(body.message, context, pending) or confirmed_recovery(body.message, pending, available)
            if plan is not None:
                pass
            elif body.message.strip() in ("停", "停止", "取消", "算了", "不用了"):
                plan = Plan(intent="STOP", skill_id=None, course_id=None)
            elif cfg.llm_provider == "mock":
                plan = mock_plan(body.message, context)
            else:
                reserve_model(db, user, turn)
                plan, response_id = model_plan(
                    body.message, context, available, pending,
                    [{k: c.get(k) for k in ("id", "skill_id", "title")} for c in actual_courses],
                    page_content,
                )
                op = db.scalar(
                    select(Operation).where(Operation.turn_id == turn.id, Operation.tool_name == "model.call")
                )
                if op:
                    op.result = {**op.result, "response_id": response_id, "prompt_version": "shared-1.1.0/intent-1.1.0"}
            if cfg.llm_provider == "mock" and pending and plan.skill_id and plan.intent == "UNKNOWN":
                if pending.get("intent") == "ADD_SKILL":
                    plan = Plan(intent="ADD_SKILL", skill_id=plan.skill_id, course_id=None)
            mark_skill(turn, "operation-execution")
            validate_plan(plan, available, actual_courses)
            requested_intent = plan.intent
            if plan.intent in ("ADD_SKILL", "ADD_SKILL_AND_OPEN_LESSON", "REMOVE_SKILL") and plan.skill_id is None:
                plan = Plan(intent="UNKNOWN", skill_id=None, course_id=None)
            corrected = correction_turn(db, user, turn, body.message, pending, plan.skill_id)
            if corrected:
                return corrected
            intent = plan.intent
            actions = []
            budget = Budget()
            if intent in ("ADD_SKILL", "ADD_SKILL_AND_OPEN_LESSON"):
                if not plan.skill_id or not db.get(Skill, plan.skill_id):
                    return response_for(
                        db, user, turn, "您想学哪一项？可以选择家庭园艺。", "UNKNOWN", "WAITING_USER"
                    )
                budget.check("library.add")
                require_tool(intent, "library.add")
                addition = add_skill(db, user, plan.skill_id)
                completed.append({"tool": "library.add", "result": addition["status"], "skill_id": plan.skill_id})
                db.add(
                    Operation(
                        turn_id=turn.id,
                        user_id=user.id,
                        tool_name="library.add",
                        idempotency_key=turn.id + ":add",
                        state="SUCCEEDED",
                        result=addition,
                    )
                )
                name = db.get(Skill, plan.skill_id).name
                reply = template("added" if addition["status"] == "added" else "already_joined", name=name)
            elif intent == "REMOVE_SKILL":
                budget.check("library.remove")
                require_tool(intent, "library.remove")
                removal = remove_skill(db, user, plan.skill_id)
                completed.append({"tool": "library.remove", "result": removal["status"], "skill_id": plan.skill_id})
                db.add(Operation(
                    turn_id=turn.id, user_id=user.id, tool_name="library.remove",
                    idempotency_key=turn.id + ":remove", state="SUCCEEDED", result=removal,
                ))
                reply = template("removed" if removal["status"] == "removed" else "not_joined", name=db.get(Skill, plan.skill_id).name)
            elif intent == "CANCEL_ACTION":
                mark_skill(turn, "failure-recovery")
                operation = undo_operation(db, user)
                if operation:
                    undo_addition(db, user, operation)
                    reply = template("undo")
                else:
                    reply = template("no_undo")
            elif intent == "STOP":
                mark_skill(turn, "failure-recovery")
                cancel_pending(db, user)
                result = response_for(db, user, turn, template("stopped"), intent)
                result["recovery"] = {"strategy": "stop", "stop_voice_followups": True}
                turn.response = dict(result)
                return result
            elif intent == "UNAVAILABLE":
                reply = template("unavailable")
            elif intent == "RECOMMEND_COURSE":
                mark_skill(turn, "course-recommendation")
                ranked = recommend_courses(db, user, plan, body.message)
                choices = ranked["recommendations"]
                if choices:
                    reply = "可以选" + "，或".join(c["title"] for c in choices) + "。您想打开哪一门？"
                elif ranked["missing_conditions"]:
                    fields = "、".join({"duration_seconds": "时长", "difficulty": "难度"}[f] for f in ranked["missing_conditions"])
                    reply = template("missing_metadata", fields=fields)
                else:
                    reply = template("no_match")
                result = response_for(db, user, turn, reply, intent, "WAITING_USER" if choices else "SUCCEEDED")
                result.update(ranked)
                if choices:
                    result["pending_clarification"] = {"intent": intent, "recommendations": choices}
                turn.response = dict(result)
                return result
            elif intent == "DISCOVER_SKILL":
                reply = template("browse")
            elif (
                intent == "CHAT" or (cfg.llm_provider == "mock" and intent == "UNKNOWN"
                and not pending
                and not any(
                    word in body.message
                    for word in ("加入", "打开", "想学", "返回", "课程", "技能", "页面", "陪练", "移除", "删除", "不学", "学习", "这个")
                ))
            ):
                budget.check("companion.chat")
                require_tool("CHAT", "companion.chat")
                previous = db.scalars(
                    select(Turn)
                    .where(Turn.user_id == user.id, Turn.agent_role == "companion", Turn.id != turn.id)
                    .order_by(Turn.created_at.desc())
                    .limit(6)
                ).all()
                history = [
                    {
                        "user": t.response.get("conversation_message", ""),
                        "assistant": t.response.get("reply", {}).get("display_text", ""),
                    }
                    for t in reversed(previous)
                ]
                reply = companion_answer(body.message, history)
                intent = "CHAT"
            else:
                reply = "您想学什么？当前可以选择家庭园艺。"
            if intent in (
                "PAUSE_PLAYER",
                "RESUME_PLAYER",
                "OPEN_HOME",
                "OPEN_SKILLS",
                "OPEN_SETTINGS",
                "OPEN_COMMUNITY",
                "DISCOVER_SKILL",
                "OPEN_LESSON",
                "ADD_SKILL_AND_OPEN_LESSON",
                "CONTINUE_LESSON",
                "START_PRACTICE",
            ):
                selected_course = None
                if intent == "CONTINUE_LESSON":
                    candidates = db.scalars(select(Progress).where(Progress.user_id == user.id).order_by(Progress.updated_at.desc())).all()
                    candidate = next((p for p in candidates if any(
                        c["id"] == p.course_id and (not plan.skill_id or c["skill_id"] == plan.skill_id)
                        for c in actual_courses
                    )), None)
                    if candidate is None:
                        return response_for(
                            db, user, turn, "还没有可继续的进度，请先选择课程。", intent, "WAITING_USER"
                        )
                    selected_course = candidate.course_id
                selected_course = selected_course or plan.course_id
                if not selected_course and body.ui_context.course_id:
                    focused = next((c for c in actual_courses if c["id"] == body.ui_context.course_id), None)
                    if focused and (not plan.skill_id or focused["skill_id"] == plan.skill_id):
                        selected_course = focused["id"]
                lesson_intents = ("OPEN_LESSON", "ADD_SKILL_AND_OPEN_LESSON", "CONTINUE_LESSON")
                if not selected_course and intent in lesson_intents:
                    first_ids = {"repotting-basics", "calligraphy-lines", "phone-composition", "rhythm-basics"}
                    choices = sorted(
                        (c for c in actual_courses if c["skill_id"] == (plan.skill_id or "home-gardening")),
                        key=lambda c: (c["id"] not in first_ids, c["id"]),
                    )
                    selected_course = choices[0]["id"] if choices else None
                if intent in lesson_intents and not selected_course:
                    return response_for(db, user, turn, partial_text(db, completed) + template("no_match"), intent,
                                        "PARTIAL" if completed else "WAITING_USER", completed=completed)
                if selected_course and intent in lesson_intents:
                    course_or_404(db, selected_course)
                payload = {"course_id": selected_course}
                action_type = "OPEN_LESSON"
                if intent in ("PAUSE_PLAYER", "RESUME_PLAYER"):
                    if body.ui_context.page != "lesson":
                        return response_for(
                            db, user, turn, "请先打开课程，才可以控制视频。", intent, "WAITING_USER"
                        )
                    action_type = intent
                    payload = {}
                if intent in (
                    "OPEN_HOME",
                    "OPEN_SKILLS",
                    "OPEN_SETTINGS",
                    "OPEN_COMMUNITY",
                    "DISCOVER_SKILL",
                ):
                    action_type = "OPEN_PAGE"
                    payload = {
                        "page": {
                            "OPEN_HOME": "home",
                            "OPEN_SKILLS": "skills",
                            "OPEN_SETTINGS": "settings",
                            "OPEN_COMMUNITY": "community",
                            "DISCOVER_SKILL": "skills",
                        }[intent],
                        "skill_id": plan.skill_id,
                    }
                if intent == "START_PRACTICE":
                    payload = {"page": "practice"}
                    action_type = "OPEN_PAGE"
                budget.check(action_type)
                require_tool(intent, action_type)
                a = Action(
                    turn_id=turn.id,
                    user_id=user.id,
                    action_type=action_type,
                    payload=payload,
                    expires_at=(datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat(),
                )
                db.add(a)
                db.flush()
                actions = [{"id": a.id, "type": action_type, "payload": payload, "expires_at": a.expires_at}]
                reply = (reply if completed else "") + (
                    template("browse")
                    if intent == "DISCOVER_SKILL"
                    else template("opening")
                )
            result = response_for(
                db,
                user,
                turn,
                reply,
                intent,
                "WAITING_UI_ACK" if actions else ("WAITING_USER" if intent == "UNKNOWN" else "SUCCEEDED"),
                actions,
                completed,
            )
            if intent == "UNKNOWN":
                mark_skill(turn, "failure-recovery")
                removing = requested_intent == "REMOVE_SKILL" or pending.get("intent") == "REMOVE_SKILL"
                joined_ids = set(db.scalars(select(Library.skill_id).where(Library.user_id == user.id))) if removing else set()
                recovery = recover(pending.get("attempts", 0), [
                    {"label": s["name"], "message": ("不再学习" if removing else "我想学") + s["name"]}
                    for s in available if not removing or s["id"] in joined_ids
                ])
                if removing and recovery["strategy"] == "clarify":
                    recovery["speech_text"] = "您想移除哪项正在学习的技能？"
                result["skill_trace"] = turn.response["skill_trace"]
                result["recovery"] = recovery
                result["pending_clarification"] = {
                    "intent": (requested_intent if requested_intent in ("ADD_SKILL", "REMOVE_SKILL") else None) or pending.get("intent")
                    or ("ADD_SKILL" if any(x in body.message for x in ("想学", "加入")) else "UNKNOWN"),
                    "attempts": recovery["attempts"],
                }
                result["choices"] = recovery["choices"]
                result["reply"]["display_text"] = recovery["speech_text"]
                result["reply"]["speech_text"] = recovery["speech_text"]
                db.get(Reply, result["reply"]["id"]).text = recovery["speech_text"]
                turn.response = dict(result)
        turn.response = {**turn.response, "conversation_message": body.message}
        # Same transaction commits business data, operation audit and reply before returning.
        for op in db.scalars(
            select(Operation).where(Operation.turn_id == turn.id, Operation.tool_name == "model.call")
        ):
            op.state = "SUCCEEDED"
        db.flush()
    except HTTPException:
        raise
    except Exception as error:
        # No provider exception bodies or raw messages are exposed.
        mark_skill(turn, "failure-recovery")
        result = response_for(
            db,
            user,
            turn,
            partial_text(db, completed) + template("failed"),
            "ERROR",
            "PARTIAL" if completed else "FAILED",
            completed=completed,
        )
        result["error_code"] = error.code if isinstance(error, ProviderError) else "TURN_FAILED"
        turn.response = dict(result)
        for op in db.scalars(
            select(Operation).where(Operation.turn_id == turn.id, Operation.tool_name == "model.call")
        ):
            op.state = "FAILED"
    return JSONResponse(result, status_code=202 if turn.state == "WAITING_UI_ACK" else 200)


def expire_actions(db, turn):
    for a in db.scalars(select(Action).where(Action.turn_id == turn.id, Action.state == "PENDING")):
        if a.expires_at < now():
            a.state = "EXPIRED"
            turn.state = "UNKNOWN"
            saved_reply = db.get(Reply, turn.response.get("reply", {}).get("id"))
            if saved_reply:
                saved_reply.text = partial_text(db, turn.response.get("completed_steps", [])) + template("page_expired")
            turn.response = {
                **turn.response,
                "state": "UNKNOWN",
                "ui_actions": [],
                "reply": {
                    **turn.response["reply"],
                    "display_text": partial_text(db, turn.response.get("completed_steps", [])) + template("page_expired"),
                    "speech_text": partial_text(db, turn.response.get("completed_steps", [])) + template("page_expired"),
                },
            }


@app.post("/api/v1/agent/ui-actions/{aid}/ack")
def ack(aid: str, body: Ack, user=Depends(current_user), db=Depends(database)):
    a = db.scalar(select(Action).where(Action.id == aid, Action.user_id == user.id).with_for_update())
    if not a:
        raise HTTPException(404, "ACTION_NOT_FOUND")
    turn = db.get(Turn, a.turn_id)
    expire_actions(db, turn)
    if a.state != "PENDING":
        return turn.response
    a.state = "APPLIED" if body.result == "applied" else "FAILED"
    completed = turn.response.get("completed_steps", [])
    if body.result == "applied":
        reply = {"PAUSE_PLAYER": "视频已暂停。", "RESUME_PLAYER": "视频已继续播放。"}.get(a.action_type) or (
            "课程已经打开。"
            if a.action_type == "OPEN_LESSON"
            else (
                "已进入独立私教陪练。"
                if a.action_type == "START_PRACTICE"
                else "已打开"
                + {
                    "home": "首页",
                    "skills": "技能广场",
                    "settings": "我的与隐私",
                    "community": "作品社区",
                    "practice": "陪练",
                }.get(a.payload.get("page"), "页面")
                + "。"
            )
        )
        state = "SUCCEEDED"
    else:
        mark_skill(turn, "failure-recovery")
        reply = partial_text(db, completed) + template("page_failed")
        state = "PARTIAL" if completed else "FAILED"
    return response_for(db, user, turn, reply, turn.response["intent"], state, completed=completed)


@app.post("/api/v1/audio/transcriptions")
async def transcription(file: UploadFile = File(...), user=Depends(current_user)):
    raw = await file.read(cfg.audio_upload_max_bytes + 1)
    await file.close()
    if len(raw) > cfg.audio_upload_max_bytes:
        raise HTTPException(413, "AUDIO_TOO_LARGE")
    allowed = {"audio/webm", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg"}
    if (file.content_type or "").split(";")[0] not in allowed:
        raise HTTPException(422, "UNSUPPORTED_AUDIO")
    duration: float | None = None
    # The frontend emits validated PCM16 WAV, avoiding optional WebM decoders.
    try:
        if raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
            import wave

            with wave.open(io.BytesIO(raw), "rb") as wav:
                duration = wav.getnframes() / wav.getframerate()
                if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
                    raise ValueError("PCM16_MONO_REQUIRED")
        else:
            media = MediaFile(io.BytesIO(raw))
            duration = media.info.length if media and media.info else None
        if duration is None:
            import shutil
            import subprocess
            import tempfile
            from pathlib import Path

            if not shutil.which("ffprobe"):
                raise ValueError("DECODER_UNAVAILABLE")
            with tempfile.TemporaryDirectory() as folder:
                p = Path(folder) / "upload.audio"
                p.write_bytes(raw)
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(p)],
                    capture_output=True,
                    timeout=5,
                    check=True,
                )
                duration = float(json.loads(probe.stdout)["format"]["duration"])
        if duration <= 0:
            raise ValueError("EMPTY_AUDIO")
    except Exception:
        raise HTTPException(422, "INVALID_AUDIO_OR_DECODER_UNAVAILABLE") from None
    if duration > cfg.audio_max_seconds:
        raise HTTPException(413, "AUDIO_TOO_LONG")
    if cfg.audio_provider == "mock":
        raise HTTPException(503, "MOCK_AUDIO_NO_REAL_TRANSCRIPTION_USE_TEXT")
    try:
        if cfg.audio_provider == "deepseek":
            result = audio_request("asr", files={"file": ("recording.wav", raw, "audio/wav")}).json()
            from .transcripts import normalize_transcript

            normalized, corrections = normalize_transcript(result["text"])
            return {
                "text": normalized,
                "corrections": corrections,
                "provider": "deepseek",
                "language": "zh-CN",
            }
        result = client().audio.transcriptions.create(
            model=cfg.openai_asr_model,
            file=(
                "recording." + ("webm" if "webm" in (file.content_type or "") else "mp4"),
                raw,
                file.content_type,
            ),
            language="zh",
        )
        return {"text": result.text, "provider": "openai", "language": "zh-CN"}
    except Exception:
        raise HTTPException(503, "ASR_UNAVAILABLE") from None


@app.post("/api/v1/audio/speech")
def speech(body: Speech, user=Depends(current_user), db=Depends(database)):
    reply = db.scalar(select(Reply).where(Reply.id == body.reply_id, Reply.user_id == user.id))
    if not reply:
        raise HTTPException(404, "REPLY_NOT_FOUND")
    if cfg.audio_provider == "mock":
        raise HTTPException(503, "MOCK_AUDIO_USE_TEXT")
    try:
        if cfg.audio_provider == "deepseek":
            result = audio_request(
                "tts", json={"text": reply.text[:600], "voice_id": cfg.deepseek_tts_voice, "format": "wav"}
            )
            return Response(normalize_wav(result.content), media_type="audio/wav")
        result = client().audio.speech.create(
            model=cfg.openai_tts_model,
            voice=cfg.openai_tts_voice,
            input=reply.text[:600],
            response_format="mp3",
        )
        return Response(result.content, media_type="audio/mpeg")
    except Exception:
        raise HTTPException(503, "TTS_UNAVAILABLE") from None


@app.post("/api/v1/telemetry", status_code=204)
def telemetry(body: Telemetry, user=Depends(current_user), db=Depends(database)):
    if set(body.properties) - {"course_id", "step_no", "error_code"}:
        raise HTTPException(422, "UNKNOWN_TELEMETRY_FIELD")
    if any(
        not isinstance(v, (int, bool)) and v not in ("repotting-basics", "PERMISSION_DENIED", "ASR_FAILED")
        for v in body.properties.values()
    ):
        raise HTTPException(422, "INVALID_TELEMETRY_VALUE")
    db.add(Event(user_id=user.id, event_name=body.event_name, properties=body.properties))


@app.delete("/api/v1/me/data", status_code=204)
def erase(body: DeleteData, user=Depends(current_user), db=Depends(database)):
    db.execute(delete(WorkMedia).where(WorkMedia.work_id.in_(select(Work.id).where(Work.user_id == user.id))))
    db.execute(delete(WorkVideo).where(WorkVideo.work_id.in_(select(Work.id).where(Work.user_id == user.id))))
    targets = select("work:" + Work.id).where(Work.user_id == user.id)
    for feed_model in (FeedReaction, FeedComment):
        db.execute(delete(feed_model).where(feed_model.target.in_(targets)))
        db.execute(delete(feed_model).where(feed_model.user_id == user.id))
    sessions = select(Practice.id).where(Practice.user_id == user.id)
    db.execute(delete(StepEvent).where(StepEvent.session_id.in_(sessions)))
    for model in (Reply, Action, Operation, Turn, Practice, Progress, Library, CompletedSkill, Event, Work):
        db.execute(delete(model).where(model.user_id == user.id))
    # Identity is retained so current JWT cannot reassign another user's data.


from .community import router as community_router  # noqa: E402

app.include_router(community_router)
from .vision import router as vision_router  # noqa: E402

app.include_router(vision_router)
from .oidc import router as oidc_router  # noqa: E402

app.include_router(oidc_router)
