"""Application skills: discoverable instructions plus deterministic, bounded policies.

Markdown informs model decisions; policies are enforced by application code. No
skill grants the model filesystem, network, or database access of its own.
"""

import hashlib
import json
import re
from pathlib import Path
from sqlalchemy import select, delete
from .config import settings
from .db import Course, Library, Progress, Skill, Operation, Action, Turn, Reply
from .schemas import Plan

ROOT = Path(__file__).parent
SKILLS = (
    "intent-recognition", "course-recommendation", "operation-execution",
    "response-generation", "failure-recovery",
)


def load_skill(name):
    if name not in SKILLS:
        raise ValueError("UNKNOWN_SKILL")
    folder = ROOT / "skills" / name
    raw = (folder / "SKILL.md").read_text("utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if not match or f"name: {name}\n" not in match[1] + "\n" or "description: " not in match[1]:
        raise ValueError("INVALID_SKILL_METADATA")
    policy_raw = (folder / "references/policy.json").read_text("utf-8")
    policy = json.loads(policy_raw)
    return {
        "name": name, "version": policy["version"], "instructions": match[2].strip(),
        "policy": policy, "sha256": hashlib.sha256((raw + policy_raw).encode()).hexdigest(),
    }


def shared_prompt():
    return (ROOT / "prompts/shared-system.md").read_text("utf-8")


def compose_prompt(*names, extra=""):
    return "\n\n".join([shared_prompt(), *(load_skill(n)["instructions"] for n in names), extra])


def mark_skill(turn, name):
    skill = load_skill(name)
    trace = dict((turn.response or {}).get("skill_trace", {}))
    trace[name] = {k: skill[k] for k in ("version", "sha256")}
    turn.response = {**(turn.response or {}), "skill_trace": trace}
    return skill["policy"]


def manifest():
    return {
        "system_prompt_sha256": hashlib.sha256(shared_prompt().encode()).hexdigest(),
        "skills": [{k: load_skill(n)[k] for k in ("name", "version", "sha256")} for n in SKILLS],
    }


def template(code, **values):
    policy = load_skill("response-generation")["policy"]
    return policy["templates"][code].format(**values)


def require_tool(intent, tool):
    allowed = load_skill("operation-execution")["policy"]["intent_tools"].get(intent, [])
    if tool not in allowed:
        raise ValueError("TOOL_NOT_ALLOWED")


def validate_plan(plan, catalog, courses=()):
    policy = load_skill("operation-execution")["policy"]
    if plan.intent not in policy["intent_tools"]:
        raise ValueError("TOOL_NOT_ALLOWED")
    ids = {s["id"] for s in catalog}
    if plan.skill_id is not None and plan.skill_id not in ids:
        raise ValueError("SKILL_NOT_FOUND")
    if plan.course_id is not None:
        course = next((c for c in courses if c["id"] == plan.course_id), None)
        if course is None or (plan.skill_id and course["skill_id"] != plan.skill_id):
            raise ValueError("COURSE_NOT_FOUND")


def course_candidates(db):
    return [
        {**c.data, "id": c.id, "skill_id": c.skill_id}
        for c in db.scalars(select(Course).order_by(Course.id))
        if settings().app_env in ("local", "test") or c.data.get("review_status") == "approved"
    ]


def recommend_courses(db, user, plan, message):
    require_tool("RECOMMEND_COURSE", "catalog.read")
    policy = load_skill("course-recommendation")["policy"]
    candidates = course_candidates(db)
    joined = {s.skill_id for s in db.scalars(select(Library).where(Library.user_id == user.id))}
    progress = {p.course_id: p for p in db.scalars(select(Progress).where(Progress.user_id == user.id))}
    names = {s.id: s.name for s in db.scalars(select(Skill))}
    duration = re.search(r"(\d+)\s*分钟", message)
    beginner = any(x in message for x in ("简单", "入门", "初学", "零基础"))
    missing = set()
    ranked = []
    for c in candidates:
        if plan.skill_id and c["skill_id"] != plan.skill_id:
            continue
        reasons, labels = [], []
        if duration:
            if not isinstance(c.get("duration_seconds"), (int, float)):
                missing.add("duration_seconds")
                continue
            if c["duration_seconds"] > int(duration[1]) * 60:
                continue
            reasons.append("DURATION_MATCH")
            labels.append("符合您说的时长")
        if beginner:
            if "difficulty" not in c:
                missing.add("difficulty")
                continue
            if c["difficulty"] != "beginner":
                continue
            reasons.append("BEGINNER")
            labels.append("课程标注为入门")
        score = 0
        if plan.skill_id:
            score += policy["weights"]["interest"]
            reasons.append("MATCHED_INTEREST")
            labels.append("属于您想学的" + names[c["skill_id"]])
        if c["id"] in progress:
            score += policy["weights"]["progress"]
            reasons.append("HAS_PROGRESS")
            labels.append("您学过这节课，可以接着练")
        elif c["skill_id"] in joined:
            score += policy["weights"]["joined"]
            reasons.append("JOINED_SKILL")
            labels.append("属于您已加入的技能")
        if not labels:
            reasons.append("AVAILABLE")
            labels.append("这节课当前可以学习")
        ranked.append({
            "course_id": c["id"], "skill_id": c["skill_id"], "title": c["title"], "score": score,
            "reason_codes": reasons, "reason_text": labels[0] + "。",
        })
    ranked.sort(key=lambda c: (-c["score"], c["course_id"]))
    return {
        "recommendations": ranked[:policy["max_options"]], "source_count": len(candidates),
        "missing_conditions": sorted(missing) if not ranked else [],
    }


def recover(attempts, choices):
    policy = load_skill("failure-recovery")["policy"]
    count = attempts + 1
    manual = count >= policy["manual_after"]
    return {
        "strategy": "manual_fallback" if manual else "clarify", "attempts": count,
        "stop_voice_followups": manual,
        "choices": choices[:policy["max_options"]],
        "speech_text": template("manual_fallback" if manual else "clarify"),
    }


def response_text(text):
    """Bound open-ended speech. Never use this to invent execution outcomes."""
    policy = load_skill("response-generation")["policy"]
    clean = text.strip()
    if not clean or any(w in clean for w in policy["forbidden_claims"]):
        return template("uncertain")
    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", clean)
    clean = "".join(sentences[:policy["max_sentences"]])
    return clean[:policy["max_chars"]]


def confirmed_recovery(message, pending, catalog):
    """Use a real pending choice; never ask the LLM to manufacture an object ID."""
    if pending.get("intent") == "RECOMMEND_COURSE":
        choices = pending.get("recommendations", [])
        selected = next((c for c in choices if c["title"] in message), None)
        if selected is None:
            indexes = {"第一": 0, "第一个": 0, "第一门": 0, "第二": 1, "第二个": 1}
            index = next((i for phrase, i in indexes.items() if phrase in message), None)
            if index is not None and index < len(choices):
                selected = choices[index]
        if selected and any(x in message for x in ("打开", "学习", "就选", "就这个")):
            return Plan(intent="OPEN_LESSON", skill_id=selected["skill_id"], course_id=selected["course_id"])
    return None


def undo_operation(db, user, expected=None):
    operation = db.scalar(
        select(Operation).where(
            Operation.user_id == user.id, Operation.tool_name == "library.add",
            Operation.state == "SUCCEEDED",
        ).order_by(Operation.created_at.desc()).limit(1).with_for_update()
    )
    if expected is not None and (not operation or operation.id != expected):
        return None
    if not operation or operation.result.get("status") != "added":
        return None
    joined = db.get(Library, (user.id, operation.result.get("skill_id")))
    # A removed-and-rejoined membership no longer belongs to this old operation.
    if not joined or joined.joined_at > operation.created_at:
        return None
    return operation


def undo_addition(db, user, operation):
    require_tool("CANCEL_ACTION", "library.undo")
    db.execute(delete(Library).where(
        Library.user_id == user.id, Library.skill_id == operation.result["skill_id"],
    ))
    operation.state = "CANCELLED"


def cancel_pending(db, user):
    require_tool("STOP", "actions.cancel")
    for action in db.scalars(select(Action).where(Action.user_id == user.id, Action.state == "PENDING")):
        action.state = "CANCELLED"
        old = db.get(Turn, action.turn_id)
        if old:
            words = partial_text(db, old.response.get("completed_steps", [])) + template("stopped")
            old.state = "PARTIAL" if old.response.get("completed_steps") else "FAILED"
            old.response = {
                **old.response, "state": old.state, "ui_actions": [],
                "reply": {**old.response["reply"], "display_text": words, "speech_text": words},
            }
            reply = db.get(Reply, old.response["reply"]["id"])
            if reply:
                reply.text = words


def partial_text(db, completed):
    ids = [s.get("skill_id") for s in completed if s.get("tool") == "library.add"]
    names = [skill.name for sid in ids if (skill := db.get(Skill, sid)) is not None]
    return template("partial", name="、".join(names)) if names else ""


def correction_turn(db, user, turn, message, pending, skill_id=None):
    """Confirmed replacement bound to the exact undoable server-side operation."""
    from .main import response_for, add_skill

    confirming = pending.get("intent") == "CONFIRM_CORRECTION"
    yes = message.strip(" 。！!，,") in ("是", "好的", "好", "确认", "确定", "是的", "对", "可以")
    if confirming and yes:
        mark_skill(turn, "failure-recovery")
        mark_skill(turn, "operation-execution")
        sid = pending["target_skill_id"]
        target = db.get(Skill, sid)
        operation = undo_operation(db, user, pending.get("operation_id")) if pending.get("operation_id") else None
        if not target or (pending.get("operation_id") and not operation):
            return response_for(db, user, turn, "刚才的操作已变化，请重新选择技能。", "UNKNOWN", "WAITING_USER")
        require_tool("ADD_SKILL", "library.add")
        if operation:
            undo_addition(db, user, operation)
        added = add_skill(db, user, sid)
        db.add(Operation(
            user_id=user.id, turn_id=turn.id, tool_name="library.add", idempotency_key=turn.id + ":add",
            state="SUCCEEDED", result=added,
        ))
        return response_for(db, user, turn, template("added" if added["status"] == "added" else "already_joined", name=target.name), "ADD_SKILL")
    if not skill_id or "不是这个" not in message or not any(x in message for x in ("想学", "换", "改成")):
        return None
    target = db.get(Skill, skill_id)
    if not target:
        return None
    mark_skill(turn, "failure-recovery")
    operation = undo_operation(db, user)
    previous = db.get(Skill, operation.result["skill_id"]) if operation else None
    text = f"要撤销刚加入的{previous.name}，改为{target.name}吗？" if previous else f"要把{target.name}加入技能库吗？"
    result = response_for(db, user, turn, text, "UNKNOWN", "WAITING_USER")
    result["pending_clarification"] = {
        "intent": "CONFIRM_CORRECTION", "target_skill_id": skill_id,
        "operation_id": operation.id if operation else None,
    }
    result["recovery"] = {"strategy": "confirm_correction", "stop_voice_followups": False}
    turn.response = dict(result)
    return result
