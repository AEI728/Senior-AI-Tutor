"""Authorization Code + PKCE, state and nonce. Token stays in HttpOnly cookie."""

import base64
import hashlib
import secrets
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from .config import settings

router = APIRouter(prefix="/api/v1/auth")


@router.get("/config")
def auth_config():
    return {"mode": settings().auth_mode, "oidc_ready": bool(settings().oidc_client_id)}


def discovery():
    cfg = settings()
    if cfg.auth_mode != "oidc" or not cfg.oidc_client_id:
        raise HTTPException(503, "OIDC_NOT_CONFIGURED")
    if not cfg.oidc_issuer.startswith("https://"):
        raise HTTPException(503, "OIDC_HTTPS_REQUIRED")
    try:
        r = httpx.get(cfg.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration", timeout=8)
        r.raise_for_status()
        d = r.json()
        if d.get("issuer") != cfg.oidc_issuer or any(
            not d.get(k, "").startswith("https://") for k in ("authorization_endpoint", "token_endpoint")
        ):
            raise ValueError("Invalid discovery")
        return d
    except Exception:
        raise HTTPException(503, "OIDC_DISCOVERY_UNAVAILABLE") from None


@router.get("/oidc/start")
def start():
    cfg = settings()
    d = discovery()
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    nonce = secrets.token_urlsafe(24)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    callback = cfg.public_api_origin.rstrip("/") + "/api/v1/auth/oidc/callback"
    response = RedirectResponse(
        d["authorization_endpoint"]
        + "?"
        + urlencode(
            {
                "client_id": cfg.oidc_client_id,
                "redirect_uri": callback,
                "response_type": "code",
                "scope": "openid profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )
    payload = jwt.encode(
        {
            "state": state,
            "verifier": verifier,
            "nonce": nonce,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "purpose": "oidc-state",
        },
        cfg.dev_jwt_secret,
        algorithm="HS256",
    )
    response.set_cookie(
        "xiaoban-oidc",
        payload,
        max_age=300,
        httponly=True,
        secure=cfg.app_env not in ("local", "test"),
        samesite="lax",
        path="/api/v1/auth/oidc",
    )
    return response


@router.get("/oidc/callback")
def callback(request: Request, code: str = "", state: str = ""):
    cfg = settings()
    d = discovery()
    try:
        saved = jwt.decode(request.cookies.get("xiaoban-oidc", ""), cfg.dev_jwt_secret, algorithms=["HS256"])
        if (
            saved.get("purpose") != "oidc-state"
            or not state
            or not secrets.compare_digest(saved["state"], state)
            or not code
        ):
            raise ValueError("Invalid state")
        form = {
            "grant_type": "authorization_code",
            "client_id": cfg.oidc_client_id,
            "code": code,
            "code_verifier": saved["verifier"],
            "redirect_uri": cfg.public_api_origin.rstrip("/") + "/api/v1/auth/oidc/callback",
        }
        if cfg.oidc_client_secret:
            form["client_secret"] = cfg.oidc_client_secret
        r = httpx.post(d["token_endpoint"], data=form, timeout=10)
        r.raise_for_status()
        token = r.json()["id_token"]
        key = jwt.PyJWKClient(cfg.oidc_jwks_url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=cfg.oidc_issuer,
            audience=cfg.oidc_audience,
            options={"require": ["exp", "sub", "iss", "aud", "nonce"]},
        )
        if not secrets.compare_digest(claims["nonce"], saved["nonce"]):
            raise ValueError("Invalid nonce")
    except Exception:
        raise HTTPException(401, "OIDC_LOGIN_FAILED") from None
    response = RedirectResponse(cfg.web_origin)
    response.set_cookie(
        "xiaoban-session",
        token,
        max_age=max(0, int(claims["exp"] - datetime.now(timezone.utc).timestamp())),
        httponly=True,
        secure=cfg.app_env not in ("local", "test"),
        samesite="lax",
        path="/api",
    )
    response.delete_cookie("xiaoban-oidc", path="/api/v1/auth/oidc")
    return response


@router.post("/logout", status_code=204)
def logout(request: Request):
    if request.cookies.get("xiaoban-session") and request.headers.get("origin") != settings().web_origin:
        raise HTTPException(403, "CSRF_ORIGIN_REQUIRED")
    response = Response(status_code=204)
    response.delete_cookie("xiaoban-session", path="/api")
    return response
