import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_speed.filtering import filter_output, result_json  # noqa: E402


def main() -> int:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if not isinstance(event, dict):
            return 0
        raw_value = event.get("toolResult", event.get("result", ""))
        raw = raw_value if isinstance(raw_value, str) else json.dumps(raw_value, ensure_ascii=False)
        args_value = event.get("toolArgs", "")
        args = args_value if isinstance(args_value, str) else json.dumps(args_value, ensure_ascii=False)
        result = filter_output(raw, args, os.environ.get("AGENT_SPEED_RAW_STORE", "~/.agent-speed-layer/raw"))
        # Observational mode: stdout is diagnostic JSON, never a host replacement payload.
        sys.stdout.buffer.write((result_json(result) + "\n").encode("utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
