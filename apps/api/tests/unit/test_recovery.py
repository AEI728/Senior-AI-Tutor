import pytest
from app.agent import Budget
from app.config import settings


def test_tool_budget_cap():
    b = Budget()
    for i in range(settings().max_tool_steps):
        b.check(str(i))
    with pytest.raises(ValueError):
        b.check("extra")


def test_deadline_stops_execution():
    b = Budget()
    b.started -= 60
    with pytest.raises(TimeoutError):
        b.check("late")
