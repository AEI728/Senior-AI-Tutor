import hashlib
import json
import time
import re
from pathlib import Path
from openai import OpenAI
from .config import settings
from .schemas import Plan
from .providers import structured, deepseek_text
from .knowledge import retrieve
from .skill_runtime import compose_prompt, response_text

PROMPTS = Path(__file__).parent / "prompts"

SKILL_ALIASES = {
    "home-gardening": ("园艺", "养花", "盆栽"),
    "calligraphy": ("书法", "写字", "练字"),
    "photography": ("摄影", "拍照"),
    "music": ("乐器", "节奏", "音乐"),
}


def learning_rule(message, context, pending=None):
    """Reliable negative commands and deictic references, before any model writes."""
    targets = [sid for sid, aliases in SKILL_ALIASES.items() if any(a in message for a in aliases)]
    deictic = any(w in message for w in ("这个", "这门", "这项", "这种", "这节"))
    negative = bool(re.search(r"(?:不想|不再|不要|不打算).{0,4}[学练]|不学|移除|退出学习|取消学习|停止学习|删掉|删除", message))
    positive = any(w in message for w in ("想学", "要学", "加入学习"))
    if re.search(r"不(?:要|想|用).{0,3}(?:移除|删除|删掉)", message):
        return Plan(intent="UNKNOWN", skill_id=None, course_id=None)
    if len(targets) > 1 and (negative or positive):
        return Plan(intent="UNKNOWN", skill_id=None, course_id=None)
    target = targets[0] if targets else context.focused_skill_id if deictic else None
    if negative and (targets or deictic or any(w in message for w in ("学习", "不学", "想学", "技能", "课程"))) and not any(w in message for w in ("支付", "转账", "学习数据", "全部数据")):
        return Plan.model_validate({"intent": "REMOVE_SKILL", "skill_id": target, "course_id": None})
    if positive and deictic and not any(w in message for w in ("不", "别", "打开")):
        return Plan.model_validate({"intent": "ADD_SKILL" if target else "UNKNOWN", "skill_id": target, "course_id": None})
    if pending and pending.get("intent") == "REMOVE_SKILL" and len(targets) == 1 and len(message) < 12 and not positive:
        return Plan.model_validate({"intent": "REMOVE_SKILL", "skill_id": targets[0], "course_id": None})
    return None


def mock_plan(message, context):
    m = message.strip()
    ruled = learning_rule(m, context)
    if ruled is not None:
        return ruled
    if any(x in m for x in ("认字", "支付", "转账")):
        return Plan(intent="UNAVAILABLE", skill_id=None, course_id=None)
    skill = next(
        (
            sid
            for sid, aliases in {
                "home-gardening": ("园艺", "养花", "盆栽"),
                "calligraphy": ("书法", "写字"),
                "photography": ("摄影", "拍照"),
                "music": ("乐器", "节奏", "音乐"),
            }.items()
            if any(a in m for a in aliases)
        ),
        context.focused_skill_id,
    )
    if m in ("停", "停止", "取消", "算了", "不用了"):
        intent = "STOP"
    elif any(x in m for x in ("撤回", "撤销", "不是这个")):
        intent = "CANCEL_ACTION"
    elif any(x in m for x in ("回首页", "返回首页", "打开首页", "回到首页")):
        intent = "OPEN_HOME"
    elif "隐私" in m or "设置" in m:
        intent = "OPEN_SETTINGS"
    elif any(x in m for x in ("社区", "作品", "发布")):
        intent = "OPEN_COMMUNITY"
    elif any(x in m for x in ("技能广场", "技能列表")):
        intent = "OPEN_SKILLS"
    elif "暂停" in m and "视频" in m:
        intent = "PAUSE_PLAYER"
    elif any(x in m for x in ("继续播放", "播放视频")):
        intent = "RESUME_PLAYER"
    elif any(x in m for x in ("推荐", "学什么好")):
        intent = "RECOMMEND_COURSE"
    elif any(x in m for x in ("看看", "有什么课", "有哪些", "浏览")):
        intent = "DISCOVER_SKILL"
    elif any(x in m for x in ("接着上次", "继续学习", "上次的")):
        intent = "CONTINUE_LESSON"
    elif "陪练" in m:
        intent = "START_PRACTICE"
    elif any(x in m for x in ("想学", "加入", "加进")) and skill:
        intent = "ADD_SKILL_AND_OPEN_LESSON" if any(x in m for x in ("打开", "第一课")) else "ADD_SKILL"
    elif "打开" in m and ("课" in m or skill):
        intent = "OPEN_LESSON"
    else:
        intent = "UNKNOWN"
    return Plan.model_validate({"intent": intent, "skill_id": skill, "course_id": None})


def client():
    c = settings()
    return OpenAI(api_key=c.openai_api_key, max_retries=0, timeout=c.openai_request_timeout_seconds)


def instructions(role):
    stage = "intent-recognition" if role == "companion" else "response-generation"
    return compose_prompt(stage, extra=(PROMPTS / f"{role}.md").read_text("utf-8"))


def openai_plan(message, context, catalog=None, pending=None, courses=None, page_content=None):
    schema = Plan.model_json_schema()
    result = client().responses.create(
        model=settings().openai_model,
        store=False,
        max_output_tokens=400,
        instructions=instructions("companion"),
        input=json.dumps(
            {
                "message": message,
                "ui_context": context.model_dump(),
                "available_catalog": catalog or [{"id": "home-gardening", "name": "家庭园艺"}],
                "pending_clarification": pending or {},
                "available_courses": courses or [],
                "page_content_untrusted": page_content,
            },
            ensure_ascii=False,
        ),
        tools=[
            {
                "type": "function",
                "name": "plan_learning_action",
                "description": "选择下一项学习操作；执行权由服务端校验。",
                "strict": True,
                "parameters": schema,
            }
        ],
        tool_choice={"type": "function", "name": "plan_learning_action"},
        parallel_tool_calls=False,
    )
    calls = [x for x in result.output if x.type == "function_call"]
    if len(calls) != 1 or calls[0].name != "plan_learning_action":
        raise ValueError("INVALID_MODEL_PLAN")
    return Plan.model_validate_json(calls[0].arguments), result.id


def model_plan(message, context, catalog, pending, courses=None, page_content=None):
    if settings().llm_provider == "deepseek":
        return structured(
            Plan,
            instructions("companion"),
            {
                "message": message,
                "ui_context": context.model_dump(),
                "available_catalog": catalog,
                "pending_clarification": pending,
                "available_courses": courses or [],
                "page_content_untrusted": page_content,
            },
        )
    return openai_plan(message, context, catalog, pending, courses, page_content)


def tutor_answer(message, course, step):
    if settings().llm_provider == "mock":
        if "土" in message or "多少" in message:
            return course["faq"][0]["answer"]
        if any(x in message for x in ("对吗", "看", "标准")):
            return "我没有摄像头画面，无法观察或判断您的动作质量。可以告诉我具体遇到什么问题。"
        if "拿不出" in message:
            return course["faq"][1]["answer"]
        return "按当前步骤慢慢来：" + step["instruction"] + " 如果信息不够，我们先停下来确认。"
    knowledge = {
        "question": message,
        "can_see_video": False,
        "course_data_untrusted": {
            "id": course["id"],
            "version": course["version"],
            "review_status": course["review_status"],
            "step": step,
            "faq": course["faq"],
        },
        "reference_data_untrusted": retrieve(course["id"], message),
    }
    if settings().llm_provider == "deepseek":
        text = deepseek_text(instructions("tutor"), knowledge).strip()
    else:
        return openai_tutor(message, course, step)
    if not text or any(x in text for x in ("我看到", "我看见", "动作很标准", "转账", "验证码")):
        return "我无法观察动作，也没有足够的课程依据判断。请先暂停，并具体说说您遇到的问题。"
    return response_text(text)


def openai_tutor(message, course, step):
    output = client().responses.create(
        model=settings().openai_model,
        store=False,
        max_output_tokens=300,
        instructions=instructions("tutor"),
        input=json.dumps(
            {
                "question": message,
                "can_see_video": False,
                "course_data_untrusted": {
                    "id": course["id"],
                    "version": course["version"],
                    "review_status": course["review_status"],
                    "step": step,
                    "faq": course["faq"],
                },
            },
            ensure_ascii=False,
        ),
    )
    text = output.output_text.strip()
    if not text or any(x in text for x in ("我看到", "我看见", "动作很标准", "转账", "验证码")):
        return "我无法观察动作，也没有足够的课程依据判断。请先暂停，并具体说说您遇到的问题。"
    return response_text(text)


def request_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Budget:
    def __init__(self):
        self.started = time.monotonic()
        self.tools = 0
        self.seen: set[str] = set()

    def check(self, name):
        self.tools += 1
        if self.tools > settings().max_tool_steps or name in self.seen:
            raise ValueError("TOOL_BUDGET_EXCEEDED")
        if (time.monotonic() - self.started) * 1000 > settings().turn_deadline_ms:
            raise TimeoutError("TURN_DEADLINE_EXCEEDED")
        self.seen.add(name)


def companion_answer(message, history):
    if settings().llm_provider == "mock":
        return "我在呢，您慢慢说。想聊聊天或一起学点喜欢的，都可以。"
    prompt = compose_prompt("response-generation", extra="当前角色是底部语音助手的闲聊模式，无摄像头，也未执行任何业务操作。结合自身最近对话自然回答；不得声称已经操作。")
    payload = {"message": message, "recent_dialogue": history}
    if settings().llm_provider == "deepseek":
        return response_text(deepseek_text(prompt, payload))
    return response_text(
        client()
        .responses.create(
            model=settings().openai_model,
            store=False,
            max_output_tokens=250,
            instructions=prompt,
            input=json.dumps(payload, ensure_ascii=False),
        )
        .output_text.strip()
    )
