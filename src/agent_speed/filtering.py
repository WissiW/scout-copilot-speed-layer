from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

READ_ONLY_COMMANDS = {
    "git status", "git diff --stat", "git log", "git branch", "git remote -v",
    "pytest", "python -m pytest", "ruff check", "npm test", "cargo test",
}
PROTECTED_MARKERS = ("traceback", "error", "exception", "failed", "secret", "token", "password", "api_key")
MAX_INPUT_BYTES = 4 * 1024 * 1024

@dataclass(frozen=True)
class FilterResult:
    text: str
    changed: bool
    raw_id: str | None
    raw_path: str | None
    reason: str


def _raw_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_safe_command(command: str) -> bool:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    if not tokens or any(token in {";", "&&", "||", "|", ">", ">>", "<"} for token in tokens):
        return False
    normalized = " ".join(tokens).lower()
    return normalized in READ_ONLY_COMMANDS or any(
        normalized.startswith(prefix + " ") and prefix in {"git status", "git log", "git branch", "pytest", "ruff check"}
        for prefix in READ_ONLY_COMMANDS
    )


def _protected(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in PROTECTED_MARKERS)


def _secure_store(store: str | Path) -> Path:
    root = Path(store).expanduser()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("raw store must be a real directory")
    return root


def _archive_text(store: str | Path, raw_id: str, text: str) -> str:
    root = _secure_store(store)
    path = root / raw_id
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise ValueError("raw archive target is unsafe")
    if not path.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)
    os.chmod(path, 0o600)
    return str(path)


def _compact_lines(text: str) -> str:
    lines = text.splitlines()
    if len(lines) < 40:
        return text
    output: list[str] = []
    repeated = 0
    previous = None
    for line in lines:
        normalized = re.sub(r"\s+", " ", line.strip())
        if normalized and normalized == previous:
            repeated += 1
            continue
        if repeated:
            output.append(f"[agent-speed: omitted {repeated} repeated lines]")
            repeated = 0
        output.append(line)
        previous = normalized
    if repeated:
        output.append(f"[agent-speed: omitted {repeated} repeated lines]")
    if len(output) >= len(lines):
        return text
    return "\n".join(output) + ("\n" if text.endswith("\n") else "")


def filter_output(text: str, command: str = "", store: str | Path | None = None, unsafe: bool = False) -> FilterResult:
    if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        return FilterResult(text, False, None, None, "input exceeds safety limit")
    raw_id = _raw_id(text)
    raw_path: str | None = None
    if store is not None:
        try:
            raw_path = _archive_text(store, raw_id, text)
        except (OSError, ValueError):
            return FilterResult(text, False, raw_id, None, "archive unavailable; original preserved")
    if not unsafe and (not _is_safe_command(command) or _protected(text)):
        return FilterResult(text, False, raw_id, raw_path, "protected or unrecognised command")
    compacted = _compact_lines(text)
    return FilterResult(compacted, compacted != text, raw_id, raw_path, "repeated-line reduction" if compacted != text else "no safe reduction")


def result_json(result: FilterResult) -> str:
    return json.dumps({
        "text": result.text,
        "changed": result.changed,
        "raw_id": result.raw_id,
        "reason": result.reason,
    }, ensure_ascii=False)
