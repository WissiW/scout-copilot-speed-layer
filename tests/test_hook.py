"""Tests for the observational Copilot hook."""
import json
import subprocess
import sys
from pathlib import Path


HOOK = Path(__file__).parents[1] / "integrations" / "copilot_filter_hook.py"


def run_hook(payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(HOOK)], input=payload, text=True, capture_output=True)


def test_hook_handles_malformed_input() -> None:
    result = run_hook("not-json")
    assert result.returncode == 0
    assert result.stdout == ""


def test_hook_does_not_emit_local_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SPEED_RAW_STORE", str(tmp_path))
    event = {"toolArgs": "git status", "toolResult": "ok"}
    result = run_hook(json.dumps(event))
    assert result.returncode == 0
    assert str(tmp_path) not in result.stdout
    assert "raw_id" in result.stdout
