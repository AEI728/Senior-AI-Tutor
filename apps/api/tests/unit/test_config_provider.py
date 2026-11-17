import pytest
from app.config import Settings


def test_deepseek_env_aliases_and_auto():
    cfg = Settings(
        _env_file=None,
        llm_provider="auto",
        audio_provider="auto",
        deepseek_api_key="test-key",
        USE_MOCK_LLM=False,
        PORT=4312,
    )
    assert cfg.llm_provider == "deepseek" and cfg.audio_provider == "deepseek" and cfg.app_port == 4312


def test_explicit_mock_beats_auto():
    cfg = Settings(
        _env_file=None,
        llm_provider="auto",
        audio_provider="auto",
        use_mock_llm=True,
        deepseek_api_key="test-key",
    )
    assert cfg.llm_provider == "mock" and cfg.audio_provider == "mock"


def test_deepseek_https():
    cfg = Settings(
        _env_file=None,
        llm_provider="deepseek",
        audio_provider="mock",
        deepseek_api_key="test-key",
        deepseek_base_url="http://bad.example",
    )
    with pytest.raises(ValueError):
        cfg.validate_runtime()
