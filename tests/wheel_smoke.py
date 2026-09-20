"""Run with a Python environment containing the installed wheel, not an editable install."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile

import agent_speed


root = Path(__file__).resolve().parents[1]
assert not Path(agent_speed.__file__).resolve().is_relative_to(root / "src")
assert agent_speed.__version__ == importlib.metadata.version("agent-speed-layer") == "0.1.2"
entry_point = Path(sysconfig.get_path("scripts")) / ("agent-speed.exe" if os.name == "nt" else "agent-speed")
assert entry_point.is_file()
env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
with tempfile.TemporaryDirectory() as temp:
    for cli in ([str(entry_point)], [sys.executable, "-I", "-m", "agent_speed.cli"]):
        for text in (
            "same\n" * 40,
            "\u00e9\u6f22\U0001f600\r\n" * 40,
            "same\r\n" * 20 + "same\n" * 20 + "last",
        ):
            original = text.encode("utf-8")
            filtered = subprocess.run(
                cli + ["filter", "--command", "git status", "--store", temp],
                input=original, capture_output=True, check=True, env=env, cwd=temp,
            )
            data = json.loads(filtered.stdout)
            assert data["changed"]
            assert data["raw_id"] == hashlib.sha256(original).hexdigest()
            retrieved = subprocess.run(
                cli + ["retrieve", "--store", temp, "--id", data["raw_id"]],
                capture_output=True, check=True, env=env, cwd=temp,
            )
            assert retrieved.stdout == original
        for bad_input in (b"[]", b"null", b"\xff"):
            rejected = subprocess.run(
                cli + ["filter", "--event", "copilot-post-tool-use", "--store", temp],
                input=bad_input, capture_output=True, env=env, cwd=temp,
            )
            assert rejected.returncode == 1
            assert set(json.loads(rejected.stdout)) == {"error"}
            assert b"Traceback" not in rejected.stderr
print("installed wheel: module and console entry points, byte recovery, and input errors passed")
