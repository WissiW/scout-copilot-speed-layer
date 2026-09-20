from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from .filtering import filter_output, result_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-speed")
    sub = parser.add_subparsers(dest="action", required=True)
    filt = sub.add_parser("filter")
    filt.add_argument("--command", default="")
    filt.add_argument("--store", default="~/.agent-speed-layer/raw")
    filt.add_argument("--event", choices=("raw", "copilot-post-tool-use"), default="raw")
    filt.add_argument("--unsafe-filter", action="store_true")
    retrieve = sub.add_parser("retrieve")
    retrieve.add_argument("--store", default="~/.agent-speed-layer/raw")
    retrieve.add_argument("--id", required=True)
    return parser


def _read_input_text() -> str:
    return sys.stdin.buffer.read().decode("utf-8")


def main() -> int:
    args = _parser().parse_args()
    if args.action == "retrieve":
        if not re.fullmatch(r"[0-9a-f]{64}", args.id):
            print(json.dumps({"error": "invalid raw result id"}))
            return 1
        path = Path(args.store).expanduser() / args.id
        if not path.is_file() or path.is_symlink():
            print(json.dumps({"error": "raw result not found"}))
            return 1
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != args.id:
            print(json.dumps({"error": "raw result integrity failure"}))
            return 2
        sys.stdout.buffer.write(content)
        return 0
    payload = _read_input_text()
    command = args.command
    text = payload
    if args.event == "copilot-post-tool-use":
        try:
            event = json.loads(payload)
            command = command or str(event.get("toolArgs", ""))
            text = str(event.get("toolResult", event.get("result", "")))
        except json.JSONDecodeError:
            pass
    result = filter_output(text, command, args.store, args.unsafe_filter)
    sys.stdout.buffer.write((result_json(result) + "\n").encode("utf-8"))
    return 0
