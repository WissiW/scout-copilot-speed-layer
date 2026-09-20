from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXACT_COMMANDS = {
    "git status",
    "git status --short",
    "git status --porcelain",
    "git diff --stat",
    "git branch",
    "git remote -v",
    "ruff check",
    "pytest",
    "python -m pytest",
    "npm test",
    "cargo test",
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
    return command in SUPPORTED_EXACT_COMMANDS


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
    encoded = text.encode("utf-8")
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise ValueError("raw archive target is unsafe")
    if not path.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as archive:
            archive.write(encoded)
    if path.read_bytes() != encoded:
        raise ValueError("raw archive integrity failure")
    os.chmod(path, 0o600)
    return str(path)


def _compact_lines(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if len(lines) < 40:
        return text
    output: list[str] = []
    repeated = 0
    previous = ""
    for line in lines:
        if line.strip() and line == previous:
            repeated += 1
            continue
        if repeated:
            ending = previous[len(previous.rstrip("\r\n")):]
            if not ending:
                return text
            output.append(f"[agent-speed: omitted {repeated} repeated lines]{ending}")
            repeated = 0
        output.append(line)
        previous = line
    if repeated:
        ending = previous[len(previous.rstrip("\r\n")):]
        if not ending:
            return text
        output.append(f"[agent-speed: omitted {repeated} repeated lines]{ending}")
    if len(output) >= len(lines):
        return text
    compacted = "".join(output)
    return compacted if len(compacted) < len(text) else text


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
