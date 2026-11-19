import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest


@pytest.fixture
def launcher():
    root = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location("startup_tasks", root / "scripts/tasks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_web_start_does_not_require_global_pnpm(launcher, monkeypatch, tmp_path):
    entry = tmp_path / "node_modules/vite/bin/vite.js"
    entry.parent.mkdir(parents=True)
    entry.touch()
    monkeypatch.setattr(launcher, "WEB", tmp_path)
    monkeypatch.setattr(
        launcher.shutil, "which", lambda name: "node.exe" if name.startswith("node") else None
    )
    command = launcher.web_command()
    assert command[:2] == ["node.exe", str(entry)] and "--strictPort" in command


def test_repeated_start_reuses_existing_services(launcher, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "api_port", lambda: "4312")
    monkeypatch.setattr(launcher, "web_command", lambda: ["node", "vite.js"])
    monkeypatch.setattr(launcher, "port_busy", lambda _: True)
    monkeypatch.setattr(launcher, "app_health", lambda _: {"status": "ok"})
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda *a, **k: pytest.fail("Must not start duplicate process")
    )
    launcher.start_local("local")
    assert "5173" in capsys.readouterr().out


def test_other_application_port_is_not_killed(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "api_port", lambda: "4312")
    monkeypatch.setattr(launcher, "web_command", lambda: ["node", "vite.js"])
    monkeypatch.setattr(launcher, "port_busy", lambda _: True)
    monkeypatch.setattr(launcher, "app_health", lambda _: None)
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda *a, **k: pytest.fail("Must fail before starting")
    )
    with pytest.raises(SystemExit, match="4312"):
        launcher.start_local("dev")


def test_partial_start_failure_cleans_owned_processes(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "api_port", lambda: "4312")
    monkeypatch.setattr(launcher, "web_command", lambda: ["node", "vite.js"])
    monkeypatch.setattr(launcher, "port_busy", lambda _: False)
    first = SimpleNamespace(pid=12345)
    calls = []

    def spawn(*a, **k):
        calls.append(a)
        if len(calls) == 2:
            raise FileNotFoundError
        return first

    cleaned = []
    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    monkeypatch.setattr(launcher, "stop_processes", lambda processes: cleaned.extend(processes))
    with pytest.raises(SystemExit):
        launcher.start_local("dev")
    assert cleaned == [first]
