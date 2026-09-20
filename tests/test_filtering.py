import json
from pathlib import Path

from agent_speed.filtering import filter_output


def test_reduces_repeated_read_only_output(tmp_path: Path) -> None:
    text = "\n".join(["ok"] * 100) + "\n"
    result = filter_output(text, "git status --short", tmp_path)
    assert result.changed
    assert "omitted 99 repeated lines" in result.text
    assert result.raw_id
    assert Path(result.raw_path).read_text() == text


def test_protects_errors(tmp_path: Path) -> None:
    text = ("Traceback (most recent call last):\n" + "error\n") * 50
    result = filter_output(text, "pytest", tmp_path)
    assert not result.changed
    assert result.text == text
    assert "protected" in result.reason


def test_protects_unknown_commands(tmp_path: Path) -> None:
    text = "\n".join(["ok"] * 100)
    result = filter_output(text, "rm -rf build", tmp_path)
    assert not result.changed


def test_archive_is_private_and_path_is_not_exposed(tmp_path: Path) -> None:
    result = filter_output("short\n", "git status", tmp_path / "raw")
    assert result.raw_path
    assert (tmp_path / "raw").stat().st_mode & 0o777 == 0o700
    assert Path(result.raw_path).stat().st_mode & 0o777 == 0o600
    payload = json.loads(__import__("agent_speed.filtering", fromlist=["result_json"]).result_json(result))
    assert "raw_path" not in payload


def test_shell_metacharacters_fail_closed(tmp_path: Path) -> None:
    text = "\n".join(["ok"] * 100)
    result = filter_output(text, "git status --short && cat secret.txt", tmp_path)
    assert not result.changed


def test_oversized_input_is_preserved(tmp_path: Path) -> None:
    text = "x" * (4 * 1024 * 1024 + 1)
    result = filter_output(text, "git status", tmp_path)
    assert not result.changed
    assert result.text == text
    assert "safety limit" in result.reason
