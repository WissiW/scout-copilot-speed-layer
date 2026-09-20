import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import pytest

from agent_speed.filtering import filter_output
CLI = [sys.executable, "-m", "agent_speed.cli"]


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
    assert Path(result.raw_path).read_bytes() == b"short\n"
    if os.name == "posix":
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


def test_command_classification_rejects_unknown_global_options(tmp_path: Path) -> None:
    text = "\n".join(["ok"] * 100)
    result = filter_output(text, "git --no-pager status --short", tmp_path)
    assert not result.changed


def test_command_classification_rejects_mutating_commands(tmp_path: Path) -> None:
    text = "\n".join(["ok"] * 100)
    for command in (
        "git branch -D example",
        "git remote remove origin",
        "ruff check --fix",
        "git status --short;echo example",
        "git diff",
    ):
        result = filter_output(text, command, tmp_path)
        assert not result.changed, command
        assert result.text == text


def test_reduction_compares_lines_exactly_and_preserves_mixed_endings(tmp_path: Path) -> None:
    text = "  ok\r\n ok\r\n  ok\n  ok\n" + "tail\r\n" * 40
    result = filter_output(text, "git status", tmp_path)
    assert result.changed
    assert result.text.startswith("  ok\r\n ok\r\n  ok\n[agent-speed: omitted 1 repeated lines]\n")
    assert "tail\r\n" in result.text


def test_cli_retrieve_returns_archived_crlf_bytes(tmp_path: Path) -> None:
    text = "first\r\n" + "repeat\r\n" * 50
    filtered = subprocess.run(
        CLI + ["filter", "--command", "git status", "--store", str(tmp_path)],
        input=text.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    data = json.loads(filtered.stdout)
    retrieved = subprocess.run(
        CLI + ["retrieve", "--store", str(tmp_path), "--id", data["raw_id"]],
        capture_output=True,
        check=True,
    )
    assert retrieved.stdout == text.encode()


def test_allowlist_preserves_supported_branch_forms_and_log_patch(tmp_path: Path) -> None:
    for command in ("git branch example", "git branch -m old new", "git branch --edit-description", "git log -p"):
        text = "same\n" * 100
        result = filter_output(text, command, tmp_path)
        assert not result.changed, command
        assert result.text == text, command


def test_allowlist_rejects_case_and_unknown_arguments(tmp_path: Path) -> None:
    text = "ok\n" * 100
    for command in ("Git status", "git status --unknown", "git --unknown status", "git diff --stat --unknown"):
        result = filter_output(text, command, tmp_path)
        assert result.text == text, command


def test_multiline_shell_command_output_is_unchanged(tmp_path: Path) -> None:
    text = "first\nsecond\n" * 30
    result = filter_output(text, "printf 'first\\nsecond\\n'", tmp_path)
    assert result.text == text


def test_repeated_lines_without_final_newline_exact_output(tmp_path: Path) -> None:
    text = "same\n" * 39 + "same"
    result = filter_output(text, "git status", tmp_path)
    assert result.changed
    assert result.text == "same\n[agent-speed: omitted 38 repeated lines]\nsame"


def test_final_distinct_unterminated_line_exact_output(tmp_path: Path) -> None:
    text = "same\n" * 40 + "last"
    result = filter_output(text, "git status", tmp_path)
    assert result.changed
    assert result.text == "same\n[agent-speed: omitted 39 repeated lines]\nlast"


def test_whitespace_difference_exact_output(tmp_path: Path) -> None:
    text = "same\nsame \nsame\n" + "tail\n" * 40
    result = filter_output(text, "git status", tmp_path)
    assert result.text.startswith("same\nsame \nsame\n")


def test_removed_commands_return_unchanged_with_compaction_sized_input(tmp_path: Path) -> None:
    text = "same\n" * 39 + "same"
    for command in ("git branch --edit-description", "git log -p"):
        result = filter_output(text, command, tmp_path)
        assert result.changed is False
        assert result.text == text


def test_cli_byte_roundtrip_preserves_line_endings_and_unicode(tmp_path: Path) -> None:
    cases = (
        ("\u00e9\n" * 40).encode("utf-8"),
        ("\u00e9\r\n" * 40).encode("utf-8"),
        ("\u00e9\r\n" * 20 + "\u00e9\n" * 20).encode("utf-8"),
        ("\u6f22\U0001f600\r\n" * 39 + "\u6f22\U0001f600").encode("utf-8"),
    )
    for original in cases:
        filtered = subprocess.run(
            CLI + ["filter", "--command", "git status", "--store", str(tmp_path)],
            input=original,
            capture_output=True,
            check=True,
        )
        data = json.loads(filtered.stdout)
        assert data["raw_id"] == hashlib.sha256(original).hexdigest()
        assert (tmp_path / data["raw_id"]).read_bytes() == original
        retrieved = subprocess.run(
            CLI + ["retrieve", "--store", str(tmp_path), "--id", data["raw_id"]],
            capture_output=True,
            check=True,
        )
        assert retrieved.stdout == original


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_exact_terminated_reduction(tmp_path: Path, ending: str) -> None:
    text = ("  same  " + ending) * 40
    result = filter_output(text, "git status", tmp_path)
    assert result.changed
    assert result.text == "  same  " + ending + "[agent-speed: omitted 39 repeated lines]" + ending


def test_newline_changes_are_not_treated_as_identical(tmp_path: Path) -> None:
    text = ("same\r\nsame\n" * 20)
    result = filter_output(text, "git status", tmp_path)
    assert not result.changed
    assert result.text == text


@pytest.mark.parametrize("command", [
    "git branch -m old new", "git branch new", "git branch --edit-description",
    "git log -p", "git status\necho example", "git status\r\necho example",
    "git --unknown status", "git status --short;echo example",
    "git status $(echo example)", "git status `echo example`",
    "git branch -M old new", "git branch -c old new", "git remote add x example",
    "ruff check --fix", "pytest --unknown", "git diff --stat --output=example",
])
def test_unsupported_commands_never_reduce(tmp_path: Path, command: str) -> None:
    text = "same\n" * 100
    result = filter_output(text, command, tmp_path)
    assert not result.changed
    assert result.text == text


@pytest.mark.parametrize("command", [
    "git status", "git status --short", "git status --porcelain",
    "git diff --stat", "git branch", "git remote -v",
    "ruff check", "pytest", "python -m pytest", "npm test", "cargo test",
])
def test_supported_commands_reduce(tmp_path: Path, command: str) -> None:
    assert filter_output("same\n" * 100, command, tmp_path).changed


def test_existing_corrupt_archive_prevents_reduction(tmp_path: Path) -> None:
    text = "same\n" * 100
    raw_id = hashlib.sha256(text.encode()).hexdigest()
    (tmp_path / raw_id).write_bytes(b"damaged")
    result = filter_output(text, "git status", tmp_path)
    assert not result.changed
    assert result.text == text
    assert result.raw_path is None
    assert result.reason == "archive unavailable; original preserved"


def test_cli_retrieve_rejects_modified_archive(tmp_path: Path) -> None:
    result = filter_output("same\n" * 100, "git status", tmp_path)
    Path(result.raw_path).write_bytes(b"modified")
    retrieved = subprocess.run(
        CLI + ["retrieve", "--store", str(tmp_path), "--id", result.raw_id],
        capture_output=True,
    )
    assert retrieved.returncode == 2
    assert json.loads(retrieved.stdout) == {"error": "raw result integrity failure"}


def test_small_repeat_runs_do_not_expand_output(tmp_path: Path) -> None:
    text = "".join(f"{index}\n{index}\n" for index in range(20))
    result = filter_output(text, "git status", tmp_path)
    assert not result.changed
    assert result.text == text


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_blank_line_separates_repeat_runs(tmp_path: Path, ending: str) -> None:
    text = ("same" + ending) * 40 + ending + ("same" + ending) * 40
    result = filter_output(text, "git status", tmp_path)
    run = "same" + ending + "[agent-speed: omitted 39 repeated lines]" + ending
    assert result.changed
    assert result.text == run + ending + run
