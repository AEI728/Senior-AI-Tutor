from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Boolean,
    JSON,
    UniqueConstraint,
    ForeignKey,
    LargeBinary,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "app_user"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    auth_subject: Mapped[str] = mapped_column(String, unique=True)


class Skill(Base):
    __tablename__ = "skill"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)


class Course(Base):
    __tablename__ = "course"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skill.id"))
    data: Mapped[dict] = mapped_column(JSON)


class Library(Base):
    __tablename__ = "learning_library"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skill.id"), primary_key=True)
    joined_at: Mapped[str] = mapped_column(String, default=now)


class CompletedSkill(Base):
    __tablename__ = "completed_skill"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skill.id"), primary_key=True)
    completed_at: Mapped[str] = mapped_column(String, default=now)


class Progress(Base):
    __tablename__ = "lesson_progress"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"), primary_key=True)
    position_seconds: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class Practice(Base):
    __tablename__ = "practice_session"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"))
    state: Mapped[str] = mapped_column(String, default="READY")
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class StepEvent(Base):
    __tablename__ = "practice_step_event"
    __table_args__ = (UniqueConstraint("session_id", "step_no"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("practice_session.id"))
    step_no: Mapped[int] = mapped_column(Integer)
    completion_source: Mapped[str] = mapped_column(String, default="user_reported")
    quality_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Turn(Base):
    __tablename__ = "agent_turn"
    __table_args__ = (UniqueConstraint("user_id", "client_request_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    client_request_id: Mapped[str] = mapped_column(String)
    agent_role: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, default="RUNNING")
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    request_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Operation(Base):
    __tablename__ = "tool_operation"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    turn_id: Mapped[str] = mapped_column(ForeignKey("agent_turn.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    tool_name: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Action(Base):
    __tablename__ = "ui_action"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    turn_id: Mapped[str] = mapped_column(ForeignKey("agent_turn.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    action_type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String, default="PENDING")
    expires_at: Mapped[str] = mapped_column(String)


class Reply(Base):
    __tablename__ = "assistant_reply"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    turn_id: Mapped[str] = mapped_column(ForeignKey("agent_turn.id"))
    text: Mapped[str] = mapped_column(String)


class Event(Base):
    __tablename__ = "telemetry_event"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    event_name: Mapped[str] = mapped_column(String)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Account(Base):
    __tablename__ = "local_account"
    username: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class Work(Base):
    __tablename__ = "community_work"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, default="PENDING")
    created_at: Mapped[str] = mapped_column(String, default=now)
    reported: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkMedia(Base):
    __tablename__ = "work_media"
    work_id: Mapped[str] = mapped_column(ForeignKey("community_work.id"), primary_key=True)
    image_data: Mapped[bytes] = mapped_column(LargeBinary)


class WorkVideo(Base):
    __tablename__ = "work_video"
    work_id: Mapped[str] = mapped_column(ForeignKey("community_work.id"), primary_key=True)
    video_data: Mapped[bytes] = mapped_column(LargeBinary)
    media_type: Mapped[str] = mapped_column(String)


class FeedReaction(Base):
    __tablename__ = "feed_reaction"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    target: Mapped[str] = mapped_column(String, primary_key=True)
    liked: Mapped[bool] = mapped_column(Boolean, default=False)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)


class FeedComment(Base):
    __tablename__ = "feed_comment"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    target: Mapped[str] = mapped_column(String, index=True)
    body: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)


engine = create_engine(
    settings().database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings().database_url else {},
)
Session = sessionmaker(engine, expire_on_commit=False)


def database():
    with Session() as db:
        with db.begin():
            yield db
