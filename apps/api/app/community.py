import hashlib
import hmac
import secrets
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response, FileResponse
from .examples import example_items, get_example, example_video
from sqlalchemy import select, delete, func
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.exc import IntegrityError
from .db import database, User, Account, Work, Course, WorkMedia, WorkVideo, FeedReaction, FeedComment
from .auth import current_user, local_token
from .schemas import Credentials, WorkInput, Moderation
from .config import settings

router = APIRouter(prefix="/api/v1")


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ":" + hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()


@router.post("/auth/register", status_code=201)
def register(body: Credentials, db=Depends(database)):
    if settings().app_env not in ("local", "test") or settings().auth_mode != "dev":
        raise HTTPException(403, "LOCAL_ACCOUNTS_ONLY")
    username = body.username.lower()
    if db.get(Account, username):
        raise HTTPException(409, "USERNAME_TAKEN")
    try:
        with db.begin_nested():
            user = User(auth_subject="xiaoban-local:account/" + username)
            db.add(user)
            db.flush()
            db.add(Account(username=username, user_id=user.id, password_hash=password_hash(body.password)))
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "USERNAME_TAKEN") from None
    return {"access_token": local_token("account/" + username), "token_type": "bearer"}


@router.post("/auth/login")
def login(body: Credentials, db=Depends(database)):
    if settings().app_env not in ("local", "test") or settings().auth_mode != "dev":
        raise HTTPException(403, "LOCAL_ACCOUNTS_ONLY")
    account = db.get(Account, body.username.lower())
    # Equal expensive work even for nonexistent accounts.
    salt = account.password_hash.split(":")[0] if account else "0" * 32
    actual = password_hash(body.password, salt)
    if not account or not hmac.compare_digest(actual, account.password_hash):
        raise HTTPException(401, "INVALID_CREDENTIALS")
    return {"access_token": local_token("account/" + account.username), "token_type": "bearer"}


def admin(user=Depends(current_user), db=Depends(database)):
    account = db.scalar(select(Account).where(Account.user_id == user.id))
    if not ((account and account.is_admin) or user.auth_subject in settings().admin_subjects.split(",")):
        raise HTTPException(403, "ADMIN_REQUIRED")
    return user


def serialize(work):
    return {
        "id": work.id,
        "title": work.title,
        "description": work.description,
        "course_id": work.course_id,
        "state": work.state,
        "created_at": work.created_at,
    }


@router.get("/community/works")
def feed(mine: bool = False, examples: bool = False, user=Depends(current_user), db=Depends(database)):
    q = (
        select(Work).where(Work.user_id == user.id)
        if mine
        else select(Work).where(Work.state == "APPROVED", Work.reported.is_(False))
    )
    result = {
        "items": [
            {
                **serialize(w),
                "is_mine": w.user_id == user.id,
                "skill_id": db.get(Course, w.course_id).skill_id,
                "likes": db.scalar(
                    select(func.count())
                    .select_from(FeedReaction)
                    .where(FeedReaction.target == "work:" + w.id, FeedReaction.liked.is_(True))
                ),
                "image_available": bool(db.get(WorkMedia, w.id)),
                "video_available": bool(db.get(WorkVideo, w.id)),
            }
            for w in db.scalars(q.order_by(Work.created_at.desc()).limit(100))
        ]
    }
    if examples and not mine:
        result["items"] += [
            {
                **item,
                "likes": db.scalar(
                    select(func.count())
                    .select_from(FeedReaction)
                    .where(FeedReaction.target == "example:" + item["id"], FeedReaction.liked.is_(True))
                ),
            }
            for item in example_items()
        ]
    return result


@router.get("/community/examples/{eid}/video")
def shared_example_video(eid: str, user=Depends(current_user)):
    return FileResponse(example_video(eid), media_type="video/mp4")


@router.post("/community/works", status_code=201)
def submit(body: WorkInput, user=Depends(current_user), db=Depends(database)):
    if not settings().community_enabled:
        raise HTTPException(403, "COMMUNITY_DISABLED")
    if not db.get(Course, body.course_id):
        raise HTTPException(404, "COURSE_NOT_FOUND")
    work = Work(user_id=user.id, title=body.title, description=body.description, course_id=body.course_id)
    db.add(work)
    db.flush()
    return serialize(work)


@router.delete("/community/works/{wid}", status_code=204)
def remove(wid: str, user=Depends(current_user), db=Depends(database)):
    w = db.get(Work, wid)
    if not w or w.user_id != user.id:
        raise HTTPException(404, "WORK_NOT_FOUND")
    db.execute(delete(WorkMedia).where(WorkMedia.work_id == wid))
    db.execute(delete(WorkVideo).where(WorkVideo.work_id == wid))
    db.execute(delete(FeedReaction).where(FeedReaction.target == "work:" + wid))
    db.execute(delete(FeedComment).where(FeedComment.target == "work:" + wid))
    db.delete(w)


@router.post("/community/works/{wid}/report", status_code=204)
def report(wid: str, user=Depends(current_user), db=Depends(database)):
    w = db.get(Work, wid)
    if not w or w.state != "APPROVED":
        raise HTTPException(404, "WORK_NOT_FOUND")
    w.reported = True
    w.state = "PENDING"


@router.get("/community/moderation")
def queue(user=Depends(admin), db=Depends(database)):
    return {
        "items": [
            {
                **serialize(w),
                "is_mine": w.user_id == user.id,
                "skill_id": db.get(Course, w.course_id).skill_id,
                "likes": db.scalar(
                    select(func.count())
                    .select_from(FeedReaction)
                    .where(FeedReaction.target == "work:" + w.id, FeedReaction.liked.is_(True))
                ),
                "image_available": bool(db.get(WorkMedia, w.id)),
                "video_available": bool(db.get(WorkVideo, w.id)),
            }
            for w in db.scalars(select(Work).where(Work.state == "PENDING").limit(100))
        ]
    }


@router.post("/community/moderation/{wid}")
def moderate(wid: str, body: Moderation, user=Depends(admin), db=Depends(database)):
    w = db.scalar(select(Work).where(Work.id == wid).with_for_update())
    if not w:
        raise HTTPException(404, "WORK_NOT_FOUND")
    w.state = "APPROVED" if body.decision == "approve" else "REJECTED"
    w.reported = False
    return serialize(w)


@router.put("/community/works/{wid}/image")
async def upload_image(
    wid: str, file: UploadFile = File(...), user=Depends(current_user), db=Depends(database)
):
    w = db.scalar(select(Work).where(Work.id == wid, Work.user_id == user.id).with_for_update())
    if not w:
        raise HTTPException(404, "WORK_NOT_FOUND")
    data = await file.read(4 * 1024 * 1024 + 1)
    await file.close()
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(413, "IMAGE_TOO_LARGE")
    import io
    from PIL import Image, ImageOps

    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP") or image.width * image.height > 16000000:
                raise ValueError("INVALID_IMAGE")
            clean = ImageOps.exif_transpose(image).convert("RGB")
            clean.thumbnail((1280, 1280))
            output = io.BytesIO()
            clean.save(output, "JPEG", quality=82)
    except Exception:
        raise HTTPException(422, "INVALID_IMAGE") from None
    media = db.get(WorkMedia, wid)
    if not media:
        db.add(WorkMedia(work_id=wid, image_data=output.getvalue()))
    else:
        media.image_data = output.getvalue()
    w.state = "PENDING"
    w.reported = False
    return {"state": "PENDING", "image_saved": True}


@router.get("/community/works/{wid}/image")
def work_image(wid: str, user=Depends(current_user), db=Depends(database)):
    w = db.get(Work, wid)
    account = db.scalar(select(Account).where(Account.user_id == user.id))
    if not w or not (
        (w.state == "APPROVED" and not w.reported) or w.user_id == user.id or (account and account.is_admin)
    ):
        raise HTTPException(404, "WORK_NOT_FOUND")
    media = db.get(WorkMedia, wid)
    if not media:
        raise HTTPException(404, "IMAGE_NOT_FOUND")
    return Response(media.image_data, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


def visible_work(db, user, wid):
    w = db.get(Work, wid)
    account = db.scalar(select(Account).where(Account.user_id == user.id))
    if not w or not (
        (w.state == "APPROVED" and not w.reported) or w.user_id == user.id or (account and account.is_admin)
    ):
        raise HTTPException(404, "WORK_NOT_FOUND")
    return w


@router.put("/community/works/{wid}/video")
async def upload_video(
    wid: str, file: UploadFile = File(...), user=Depends(current_user), db=Depends(database)
):
    import json
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    w = db.get(Work, wid)
    if not w or w.user_id != user.id:
        raise HTTPException(404, "WORK_NOT_FOUND")
    data = await file.read(30 * 1024 * 1024 + 1)
    await file.close()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(413, "VIDEO_TOO_LARGE")
    probe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not probe and not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError):
            raise HTTPException(503, "VIDEO_VALIDATOR_UNAVAILABLE") from None
    try:
        with tempfile.TemporaryDirectory(prefix="xiaoban-video-") as folder:
            path = Path(folder) / "upload.bin"
            path.write_bytes(data)
            if not probe:
                assert ffmpeg is not None
                media_type = (
                    "video/mp4"
                    if data[4:8] == b"ftyp"
                    else "video/webm"
                    if data[:4] == b"\x1aE\xdf\xa3"
                    else ""
                )
                if not media_type:
                    raise ValueError("INVALID_VIDEO")
                subprocess.run(
                    [
                        ffmpeg,
                        "-v",
                        "error",
                        "-i",
                        str(path),
                        "-map",
                        "0:v:0",
                        "-frames:v",
                        "1",
                        "-f",
                        "null",
                        "-",
                    ],
                    capture_output=True,
                    timeout=8,
                    check=True,
                )
                info = None
            else:
                result = subprocess.run(
                    [probe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                    capture_output=True,
                    timeout=8,
                    check=True,
                )
                info = json.loads(result.stdout)
        if info is not None:
            names = info.get("format", {}).get("format_name", "").split(",")
            media_type = "video/webm" if "webm" in names else "video/mp4" if "mp4" in names else ""
            videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
            duration = float(info.get("format", {}).get("duration", 0))
            if not media_type or not videos or duration <= 0 or duration > 300:
                raise ValueError("INVALID_VIDEO")
    except (ValueError, subprocess.SubprocessError, OSError):
        raise HTTPException(422, "INVALID_VIDEO") from None
    media = db.get(WorkVideo, wid)
    if media:
        media.video_data, media.media_type = data, media_type
    else:
        db.add(WorkVideo(work_id=wid, video_data=data, media_type=media_type))
    w.state, w.reported = "PENDING", False
    return {"state": "PENDING", "video_saved": True}


@router.get("/community/works/{wid}/video")
def work_video(wid: str, user=Depends(current_user), db=Depends(database)):
    visible_work(db, user, wid)
    media = db.get(WorkVideo, wid)
    if not media:
        raise HTTPException(404, "VIDEO_NOT_FOUND")
    return Response(
        media.video_data, media_type=media.media_type, headers={"Cache-Control": "private, no-store"}
    )


@router.get("/community/works/{wid}/thumbnail")
def work_thumbnail(wid: str, user=Depends(current_user), db=Depends(database)):
    visible_work(db, user, wid)
    image = db.get(WorkMedia, wid)
    if image:
        return Response(
            image.image_data, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"}
        )
    video = db.get(WorkVideo, wid)
    if not video:
        raise HTTPException(404, "THUMBNAIL_NOT_FOUND")
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError):
            raise HTTPException(503, "THUMBNAIL_UNAVAILABLE") from None
    assert ffmpeg is not None
    try:
        with tempfile.TemporaryDirectory(prefix="xiaoban-thumbnail-") as folder:
            path = Path(folder) / "video.bin"
            path.write_bytes(video.video_data)
            result = subprocess.run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-ss",
                    "0.1",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=480:-2",
                    "-f",
                    "image2pipe",
                    "-c:v",
                    "mjpeg",
                    "pipe:1",
                ],
                capture_output=True,
                timeout=10,
                check=True,
            )
        if not result.stdout.startswith(b"\xff\xd8"):
            raise ValueError()
    except (OSError, ValueError, subprocess.SubprocessError):
        raise HTTPException(503, "THUMBNAIL_UNAVAILABLE") from None
    try:
        with db.begin_nested():
            db.add(WorkMedia(work_id=wid, image_data=result.stdout))
            db.flush()
    except IntegrityError:
        pass
    return Response(result.stdout, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


def thread_target(db, user, target):
    kind, _, key = target.partition(":")
    if kind == "example":
        get_example(key)
    elif kind == "work":
        visible_work(db, user, key)
    elif kind != "course" or not db.get(Course, key):
        raise HTTPException(404, "THREAD_NOT_FOUND")
    return target


class ReactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    liked: bool
    saved: bool


class CommentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    body: str = Field(min_length=1, max_length=500)


@router.get("/community/threads/{target}")
def thread(target: str, user=Depends(current_user), db=Depends(database)):
    thread_target(db, user, target)
    reaction = db.get(FeedReaction, (user.id, target))
    likes = db.scalar(
        select(func.count())
        .select_from(FeedReaction)
        .where(FeedReaction.target == target, FeedReaction.liked.is_(True))
    )
    comments = db.scalars(
        select(FeedComment).where(FeedComment.target == target).order_by(FeedComment.created_at).limit(100)
    ).all()
    return {
        "liked": bool(reaction and reaction.liked),
        "saved": bool(reaction and reaction.saved),
        "likes": likes,
        "comments": [
            {"id": c.id, "body": c.body, "own": c.user_id == user.id, "created_at": c.created_at}
            for c in comments
        ],
    }


@router.put("/community/threads/{target}/reaction")
def react(target: str, body: ReactionInput, user=Depends(current_user), db=Depends(database)):
    thread_target(db, user, target)
    reaction = db.get(FeedReaction, (user.id, target))
    if not reaction:
        reaction = FeedReaction(user_id=user.id, target=target)
        db.add(reaction)
    reaction.liked, reaction.saved = body.liked, body.saved
    db.flush()
    return thread(target, user, db)


@router.post("/community/threads/{target}/comments", status_code=201)
def comment(target: str, body: CommentInput, user=Depends(current_user), db=Depends(database)):
    thread_target(db, user, target)
    c = FeedComment(user_id=user.id, target=target, body=body.body)
    db.add(c)
    db.flush()
    return {"id": c.id, "body": c.body, "own": True, "created_at": c.created_at}


@router.delete("/community/comments/{cid}", status_code=204)
def remove_comment(cid: str, user=Depends(current_user), db=Depends(database)):
    c = db.get(FeedComment, cid)
    if not c or c.user_id != user.id:
        raise HTTPException(404, "COMMENT_NOT_FOUND")
    db.delete(c)
