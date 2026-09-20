from pathlib import Path
import json
import subprocess

text = "\n".join(["ok"] * 100) + "\n"
run = subprocess.run(
    ["agent-speed", "filter", "--command", "git status --short"],
    input=text,
    text=True,
    capture_output=True,
    check=True,
)
data = json.loads(run.stdout)
assert data["changed"] is True
assert "omitted 99 repeated lines" in data["text"]
assert data["raw_id"]
raw_path = Path("~/.agent-speed-layer/raw").expanduser() / data["raw_id"]
assert raw_path.read_text() == text
retrieved = subprocess.run(
    ["agent-speed", "retrieve", "--store", "~/.agent-speed-layer/raw", "--id", data["raw_id"]],
    text=True,
    capture_output=True,
    check=True,
)
assert retrieved.stdout == text
print("smoke: reduction, raw archive, and exact retrieval passed")
