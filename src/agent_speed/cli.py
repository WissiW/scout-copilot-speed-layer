from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys

from .filtering import filter_output, result_json
from .events import parse_copilot_event
from .archive import read_archive


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-speed")
    sub = parser.add_subparsers(dest="action", required=True)
    filt = sub.add_parser("filter")
    filt.add_argument("--command", default="")
    filt.add_argument("--store", default="~/.agent-speed-layer/raw")
    filt.add_argument("--event", choices=("raw", "copilot-post-tool-use"), default="raw")
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
        try:
            content = read_archive(args.store, args.id)
        except FileNotFoundError:
            print(json.dumps({"error": "raw result not found"}))
            return 1
        except (OSError, ValueError):
            print(json.dumps({"error": "raw archive unavailable"}))
            return 1
        if hashlib.sha256(content).hexdigest() != args.id:
            print(json.dumps({"error": "raw result integrity failure"}))
            return 2
        sys.stdout.buffer.write(content)
        return 0
    try:
        payload = _read_input_text()
    except UnicodeDecodeError:
        print(json.dumps({"error": "input must be valid UTF-8"}))
        return 1
    command = args.command
    text = payload
    if args.event == "copilot-post-tool-use":
        try:
            text, event_command = parse_copilot_event(payload)
            command = command or event_command
        except (json.JSONDecodeError, RecursionError):
            print(json.dumps({"error": "Copilot event must be valid JSON"}))
            return 1
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            return 1
    result = filter_output(text, command, args.store)
    sys.stdout.buffer.write((result_json(result) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
