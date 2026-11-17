import hashlib
import hmac
import secrets
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .db import database, User, Account, Work, Course, WorkMedia
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
def feed(mine: bool = False, user=Depends(current_user), db=Depends(database)):
    q = (
        select(Work).where(Work.user_id == user.id)
        if mine
        else select(Work).where(Work.state == "APPROVED", Work.reported.is_(False))
    )
    return {
        "items": [
            {**serialize(w), "image_available": bool(db.get(WorkMedia, w.id))}
            for w in db.scalars(q.order_by(Work.created_at.desc()).limit(100))
        ]
    }


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
            {**serialize(w), "image_available": bool(db.get(WorkMedia, w.id))}
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
