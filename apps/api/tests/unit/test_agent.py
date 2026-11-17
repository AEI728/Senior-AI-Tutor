import pytest
from app.agent import mock_plan, Budget
from app.schemas import Context, Plan
from app.config import Settings


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("我想看看园艺有什么课", "DISCOVER_SKILL"),
        ("我想学养花", "ADD_SKILL"),
        ("我想学认字", "UNAVAILABLE"),
        ("把园艺加进来，再打开第一课", "ADD_SKILL_AND_OPEN_LESSON"),
        ("不是这个，撤回", "CANCEL_ACTION"),
        ("帮我公开发布作品", "OPEN_COMMUNITY"),
        ("不知道", "UNKNOWN"),
        ("接着上次的", "CONTINUE_LESSON"),
    ],
)
def test_intent(message, intent):
    assert mock_plan(message, Context()).intent == intent


def test_deictic_context():
    assert mock_plan("这个我想学", Context()).intent == "UNKNOWN"
    assert mock_plan("这个我想学", Context(focused_skill_id="home-gardening")).intent == "ADD_SKILL"


def test_budget_stops_repeat():
    b = Budget()
    b.check("library.add")
    with pytest.raises(ValueError):
        b.check("library.add")


def test_tool_schema_strict():
    schema = Plan.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize(
    "overrides",
    [{"app_env": "production"}, {"auth_mode": "oidc"}, {"llm_provider": "openai", "openai_api_key": ""}],
)
def test_runtime_guard(overrides):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **overrides).validate_runtime()
