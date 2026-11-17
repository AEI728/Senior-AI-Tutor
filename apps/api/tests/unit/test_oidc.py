from urllib.parse import urlsplit, parse_qs
from types import SimpleNamespace
from fastapi import HTTPException
import pytest
import jwt
from app import oidc


def test_pkce_start_state_nonce_and_secure_cookie(monkeypatch):
    cfg = SimpleNamespace(
        auth_mode="oidc",
        oidc_client_id="test-client",
        oidc_issuer="https://identity.example",
        public_api_origin="https://learning.example",
        web_origin="https://learning.example",
        dev_jwt_secret="only-for-local-oidc-unit-test-32-characters",
        app_env="production",
    )
    monkeypatch.setattr(oidc, "settings", lambda: cfg)
    monkeypatch.setattr(
        oidc, "discovery", lambda: {"authorization_endpoint": "https://identity.example/authorize"}
    )
    response = oidc.start()
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"] and query["state"] and query["nonce"]
    assert "HttpOnly" in response.headers["set-cookie"] and "Secure" in response.headers["set-cookie"]
    raw = response.headers["set-cookie"].split("=", 1)[1].split(";", 1)[0]
    saved = jwt.decode(raw, cfg.dev_jwt_secret, algorithms=["HS256"])
    assert saved["purpose"] == "oidc-state" and saved["state"] == query["state"][0]


def test_unconfigured_oidc_does_not_redirect_to_fake_login(monkeypatch):
    monkeypatch.setattr(oidc, "settings", lambda: SimpleNamespace(auth_mode="dev", oidc_client_id=""))
    with pytest.raises(HTTPException) as error:
        oidc.discovery()
    assert error.value.status_code == 503
