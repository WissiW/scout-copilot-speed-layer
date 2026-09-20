import json


def parse_copilot_event(payload: str) -> tuple[str, str]:
    event = json.loads(payload)
    if not isinstance(event, dict):
        raise ValueError("Copilot event must be a JSON object")
    raw = event.get("toolResult", event.get("result", ""))
    args = event.get("toolArgs", "")
    values = (
        raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False),
        args if isinstance(args, str) else json.dumps(args, ensure_ascii=False),
    )
    try:
        for value in values:
            value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Copilot event must contain valid Unicode text") from exc
    return values
