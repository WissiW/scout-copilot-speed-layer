import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_speed.filtering import filter_output, result_json  # noqa: E402
from agent_speed.events import parse_copilot_event  # noqa: E402


def main() -> int:
    try:
        raw, args = parse_copilot_event(sys.stdin.buffer.read().decode("utf-8"))
        result = filter_output(raw, args, os.environ.get("AGENT_SPEED_RAW_STORE", "~/.agent-speed-layer/raw"))
        # Observational mode: stdout is diagnostic JSON, never a host replacement payload.
        sys.stdout.buffer.write((result_json(result) + "\n").encode("utf-8"))
    except (OSError, ValueError, RecursionError):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
