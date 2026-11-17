from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from .config import settings
from .db import User, database

bearer = HTTPBearer(auto_error=False)
jwks_clients: dict[str, jwt.PyJWKClient] = {}


def local_token(subject="demo-user"):
    t = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iss": "xiaoban-local",
            "aud": "xiaoban-api",
            "sub": subject,
            "iat": t,
            "exp": t + timedelta(hours=4),
        },
        settings().dev_jwt_secret,
        algorithm="HS256",
    )


def current_user(
    request: Request, cred: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(database)
):
    token = cred.credentials if cred else request.cookies.get("xiaoban-session")
    if not token:
        raise HTTPException(401, "AUTH_REQUIRED")
    if (
        not cred
        and request.method not in ("GET", "HEAD")
        and request.headers.get("origin") != settings().web_origin
    ):
        raise HTTPException(403, "CSRF_ORIGIN_REQUIRED")
    cfg = settings()
    try:
        if cfg.auth_mode == "dev":
            claims = jwt.decode(
                token,
                cfg.dev_jwt_secret,
                algorithms=["HS256"],
                audience="xiaoban-api",
                issuer="xiaoban-local",
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        else:
            client = jwks_clients.setdefault(cfg.oidc_jwks_url, jwt.PyJWKClient(cfg.oidc_jwks_url))
            key = client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=cfg.oidc_audience,
                issuer=cfg.oidc_issuer,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
    except jwt.PyJWTError:
        raise HTTPException(401, "INVALID_TOKEN") from None
    subject = claims["iss"] + ":" + claims["sub"]
    user = db.scalar(select(User).where(User.auth_subject == subject))
    if not user:
        user = User(auth_subject=subject)
        db.add(user)
        db.flush()
    import hashlib

    request.state.user_pseudonym = hashlib.sha256(user.id.encode()).hexdigest()[:16]
    return user
