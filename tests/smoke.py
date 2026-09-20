from pathlib import Path
import json
import subprocess
import sys
import tempfile

text = "\n".join(["ok"] * 100) + "\n"
cli = [sys.executable, "-m", "agent_speed.cli"]
with tempfile.TemporaryDirectory() as store:
    run = subprocess.run(
        cli + ["filter", "--command", "git status --short", "--store", store],
        input=text.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    data = json.loads(run.stdout)
    assert data["changed"] is True
    assert "omitted 99 repeated lines" in data["text"]
    assert data["raw_id"]
    raw_path = Path(store) / data["raw_id"]
    assert raw_path.read_bytes() == text.encode()
    retrieved = subprocess.run(
        cli + ["retrieve", "--store", store, "--id", data["raw_id"]],
        capture_output=True,
        check=True,
    )
    assert retrieved.stdout == text.encode("utf-8")
print("smoke: reduction, isolated raw archive, and exact retrieval passed")
