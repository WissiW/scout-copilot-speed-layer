import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


CLI = [sys.executable, "-m", "agent_speed.cli"]


@pytest.mark.parametrize("payload", [
    b"[]", b"null", b"true", b"123", b'"text"', b"not-json", b"{",
    b'{"toolResult":"\\ud800"}', b"[" * 1500 + b"]" * 1500,
])
def test_invalid_event_is_controlled(tmp_path: Path, payload: bytes) -> None:
    result = subprocess.run(
        CLI + ["filter", "--event", "copilot-post-tool-use", "--store", str(tmp_path)],
        input=payload, capture_output=True,
    )
    assert result.returncode == 1
    assert set(json.loads(result.stdout)) == {"error"}
    assert b"Traceback" not in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("mode", ["raw", "copilot-post-tool-use"])
def test_invalid_utf8_is_controlled(tmp_path: Path, mode: str) -> None:
    result = subprocess.run(
        CLI + ["filter", "--event", mode, "--store", str(tmp_path)],
        input=b"\xff\xfe", capture_output=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"error": "input must be valid UTF-8"}
    assert b"Traceback" not in result.stderr
    assert not list(tmp_path.iterdir())


def test_module_entry_point_actually_filters_and_retrieves(tmp_path: Path) -> None:
    original = b"same\r\n" * 40
    result = subprocess.run(
        CLI + ["filter", "--command", "git status", "--store", str(tmp_path)],
        input=original, capture_output=True, check=True,
    )
    data = json.loads(result.stdout)
    assert data["changed"]
    assert data["raw_id"] == hashlib.sha256(original).hexdigest()
    retrieved = subprocess.run(
        CLI + ["retrieve", "--id", data["raw_id"], "--store", str(tmp_path)],
        capture_output=True, check=True,
    )
    assert retrieved.stdout == original


def test_unsafe_cli_override_is_not_available(tmp_path: Path) -> None:
    result = subprocess.run(
        CLI + ["filter", "--unsafe-filter", "--store", str(tmp_path)],
        input=b"same\n" * 40, capture_output=True,
    )
    assert result.returncode == 2
    assert b"unrecognized arguments: --unsafe-filter" in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("value", ["same\n" * 40, {"status": "ok"}, None, [1, 2]])
def test_cli_and_hook_event_text_agree(tmp_path: Path, value) -> None:
    payload = json.dumps({"toolArgs": "git status", "toolResult": value}).encode()
    result = subprocess.run(
        CLI + ["filter", "--event", "copilot-post-tool-use", "--store", str(tmp_path)],
        input=payload, capture_output=True, check=True,
    )
    data = json.loads(result.stdout)
    expected = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    assert (tmp_path / data["raw_id"]).read_bytes() == expected.encode()
