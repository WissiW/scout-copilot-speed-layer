"""Tests for the observational Copilot hook."""
import json
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest


HOOK = Path(__file__).parents[1] / "integrations" / "copilot_filter_hook.py"
HOOK_RUNNERS = [[sys.executable, str(HOOK)]]
if os.name == "nt":
    for shell in ("powershell.exe", "pwsh"):
        executable = shutil.which(shell)
        if executable:
            HOOK_RUNNERS.append([
                executable, "-NoProfile", "-NonInteractive", "-File",
                str(HOOK.with_name("windows-post-tool-use-hook.template.ps1")),
                "-Python", sys.executable,
            ])


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


@pytest.mark.parametrize("runner", HOOK_RUNNERS)
def test_hook_preserves_utf8_and_raw_bytes(tmp_path: Path, monkeypatch, runner: list[str]) -> None:
    monkeypatch.setenv("AGENT_SPEED_RAW_STORE", str(tmp_path))
    command = runner + (["-RawStore", str(tmp_path)] if runner[0] != sys.executable else [])
    text = ("\u00e9\u6f22\U0001f600\r\n" * 40) + "last"
    payload = json.dumps({"toolArgs": "git status", "toolResult": text}, ensure_ascii=False).encode("utf-8")
    result = subprocess.run(command, input=payload, capture_output=True, check=True)
    data = json.loads(result.stdout)
    assert data["changed"]
    assert data["raw_id"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert (tmp_path / data["raw_id"]).read_bytes() == text.encode("utf-8")
    assert set(data) == {"text", "changed", "raw_id", "reason"}


@pytest.mark.parametrize("runner", HOOK_RUNNERS)
@pytest.mark.parametrize("payload", [
    b"not-json", b"[]", b"null", b"true", b'"text"', b"\xff",
    b'{"toolArgs":"git status","toolResult":"\xff"}',
    b'{"toolResult":"\\ud800"}', b"[" * 1500 + b"]" * 1500,
])
def test_hook_ignores_malformed_events(tmp_path: Path, monkeypatch, runner: list[str], payload: bytes) -> None:
    monkeypatch.setenv("AGENT_SPEED_RAW_STORE", str(tmp_path))
    command = runner + (["-RawStore", str(tmp_path)] if runner[0] != sys.executable else [])
    result = subprocess.run(command, input=payload, capture_output=True)
    assert result.returncode == 0
    assert result.stdout == b""
    assert not list(tmp_path.iterdir())
