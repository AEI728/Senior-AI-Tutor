from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Context(Strict):
    page: str = "home"
    skill_id: str | None = None
    course_id: str | None = None
    focused_skill_id: str | None = None
    last_visible_action_id: str | None = None


class TurnInput(Strict):
    agent_role: Literal["companion", "tutor"]
    client_request_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    ui_context: Context = Field(default_factory=Context)
    practice_session_id: str | None = None


class Plan(Strict):
    intent: Literal[
        "ADD_SKILL",
        "DISCOVER_SKILL",
        "OPEN_LESSON",
        "ADD_SKILL_AND_OPEN_LESSON",
        "CONTINUE_LESSON",
        "START_PRACTICE",
        "CANCEL_ACTION",
        "UNKNOWN",
        "UNAVAILABLE",
        "OPEN_HOME",
        "OPEN_SKILLS",
        "OPEN_SETTINGS",
        "OPEN_COMMUNITY",
        "PAUSE_PLAYER",
        "RESUME_PLAYER",
        "RECOMMEND_COURSE",
        "CHAT",
        "STOP",
    ]
    skill_id: Literal["home-gardening", "calligraphy", "photography", "music"] | None
    course_id: str | None


class TutorDecision(Strict):
    action: Literal["ANSWER", "COMPLETE", "PAUSE", "RESUME", "REPEAT", "STOP", "SLOW", "CLARIFY"]


class Credentials(Strict):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=10, max_length=128)


class WorkInput(Strict):
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)
    course_id: str
    publish_confirmation: Literal["SHARE_THIS_WORK"]


class Moderation(Strict):
    decision: Literal["approve", "reject"]


class ProgressInput(Strict):
    position_seconds: int = Field(ge=0, le=86400)
    current_step: int = Field(ge=1, le=5)


class PracticeInput(Strict):
    course_id: str


class Command(Strict):
    command: Literal["START", "PAUSE", "RESUME", "STOP"]


class Ack(Strict):
    result: Literal["applied", "failed"]
    error_code: str | None = Field(default=None, max_length=80)


class Speech(Strict):
    reply_id: str


class DeleteData(Strict):
    confirmation: Literal["DELETE_MY_DATA"]


class Telemetry(Strict):
    event_name: Literal["lesson_opened", "practice_started", "user_reported_complete", "audio_failed"]
    properties: dict = Field(default_factory=dict)


class CourseStep(Strict):
    no: int
    title: str
    instruction: str
    explanation: str
    safety_notes: list[str]
    completion_rule: str
    source_role: Literal["platform_editor", "expert", "peer"]


class CourseFAQ(Strict):
    step_no: int
    question: str
    answer: str
    verified: bool


class CourseDetail(Strict):
    id: str
    skill_id: str
    title: str
    version: int
    review_status: Literal["draft", "approved"]
    asset_license_status: str
    locale: str
    media_path: str | None
    media_url: str | None
    learning_goal: str
    prerequisites: list[str]
    steps: list[CourseStep]
    faq: list[CourseFAQ]
