from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices, model_validator

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: str = "local"
    database_url: str = "sqlite:///" + (ROOT / "local-preview.db").as_posix()
    web_origin: str = "http://localhost:5173"
    auth_mode: str = "dev"
    dev_jwt_secret: str = "CHANGE_ONLY_LOCALLY_NOT_FOR_PRODUCTION_AT_LEAST_32_CHARACTERS"
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    public_api_origin: str = "http://localhost:8000"
    llm_provider: str = "auto"
    audio_provider: str = "auto"
    use_mock_llm: bool | None = None
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_tts_voice: str = "stella"
    knowledge_base_path: str = ""
    rag_top_k: int = Field(default=3, ge=1, le=5)
    app_port: int = Field(default=8000, validation_alias=AliasChoices("APP_PORT", "PORT"))
    provider_timeout_seconds: float = 20
    max_retry_attempts: int = Field(default=2, ge=0, le=2)
    community_enabled: bool = True
    upload_dir: str = str(ROOT / "uploads")
    admin_subjects: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-6-luna"
    openai_asr_model: str = "gpt-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "coral"
    openai_request_timeout_seconds: float = 8
    max_tool_steps: int = 6
    max_model_calls: int = 3
    turn_deadline_ms: int = 12000
    audio_upload_max_bytes: int = 6291456
    audio_max_seconds: int = 20
    requests_per_minute: int = 60
    model_calls_per_day: int = 100

    @model_validator(mode="after")
    def resolve_providers(self):
        if self.llm_provider == "auto":
            if self.use_mock_llm is True:
                self.llm_provider = "mock"
            elif self.deepseek_api_key:
                self.llm_provider = "deepseek"
            elif self.openai_api_key:
                self.llm_provider = "openai"
            elif self.use_mock_llm is False:
                raise ValueError("USE_MOCK_LLM=false requires a configured model key")
            else:
                self.llm_provider = "mock"
        if self.audio_provider == "auto":
            self.audio_provider = (
                "deepseek"
                if self.deepseek_api_key and self.llm_provider != "mock"
                else ("openai" if self.openai_api_key and self.llm_provider != "mock" else "mock")
            )
        return self

    def validate_runtime(self):
        if self.llm_provider not in ("mock", "openai", "deepseek") or self.audio_provider not in (
            "mock",
            "openai",
            "deepseek",
        ):
            raise ValueError("Unknown provider")
        if self.auth_mode not in ("dev", "oidc"):
            raise ValueError("Unknown auth mode")
        if self.auth_mode == "oidc" and not all((self.oidc_issuer, self.oidc_audience, self.oidc_jwks_url)):
            raise ValueError("OIDC configuration required")
        if self.app_env not in ("local", "test"):
            if self.auth_mode != "oidc" or self.llm_provider == "mock" or self.audio_provider == "mock":
                raise ValueError("External deployment refuses dev auth / mock providers")
            if "sqlite" in self.database_url or "xiaoban_local_only" in self.database_url:
                raise ValueError("External deployment requires private PostgreSQL credentials")
            if self.dev_jwt_secret.startswith("CHANGE"):
                raise ValueError("Replace default secret before deployment")
        if "openai" in (self.llm_provider, self.audio_provider) and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY required; no implicit mock fallback")
        if "deepseek" in (self.llm_provider, self.audio_provider):
            if not self.deepseek_api_key:
                raise ValueError("DEEPSEEK_API_KEY required; no implicit mock fallback")
            from urllib.parse import urlsplit

            u = urlsplit(self.deepseek_base_url)
            if u.scheme != "https" or not u.hostname or u.username or u.password:
                raise ValueError("DeepSeek endpoint must use HTTPS without URL credentials")


@lru_cache
def settings():
    value = Settings()
    value.validate_runtime()
    return value
