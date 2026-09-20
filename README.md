# Agent Speed Layer

A local, open-source sidecar for Scout and GitHub Copilot CLI. It reduces repetitive tool output before it reaches an agent while preserving the raw result for recovery.

## Version 0.1.2: deterministic MVP

The MVP is deliberately narrow and safe:

- No Jev, API key, model, daemon, or network dependency.
- Deterministic repeated-line reduction for selected read-only commands.
- Original output is stored locally before reduction.
- Command classification validates the complete argument list for each supported read-only command; permissive command-prefix matching is not used.
- Full `git diff` output remains unchanged. Only the explicit `git diff --stat` form is eligible for reduction.
- Repeated-line reduction compares complete lines, including whitespace and line endings. Retained lines and the final-newline state are preserved.
- Raw archive retrieval reads and verifies bytes, so CRLF content is returned exactly.
- The Windows PowerShell hook template is documented and observational only; it is not installed or registered.

## Design

```text
Scout / Copilot
      |
      v
agent-speed filter  -->  compact result + raw local archive
      |
      v
existing model and executor
```

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

On Windows, create the environment with `python -m venv .venv` and install with
`.\.venv\Scripts\python.exe -m pip install -e ".[test]"`.

## Use

```bash
printf '%s' "$TOOL_OUTPUT" | agent-speed filter --command 'git status --short'
agent-speed retrieve --store ~/.agent-speed-layer/raw --id SHA256_ID
```

The filter emits JSON with `text`, `changed`, `raw_id`, and `reason`. The filesystem path is intentionally not emitted.

Input and JSON output use UTF-8. Retrieval writes the archived bytes directly;
use a binary pipe or file consumer if byte-for-byte preservation is required.
Unknown arguments pass through unchanged rather than guessing whether they are safe.
Malformed event JSON, non-object events, and invalid UTF-8 produce a JSON error
and exit code 1 without creating an archive. The observational hook ignores
malformed input without emitting a host replacement payload.

The CLI is also available as `python -m agent_speed.cli`. There is no unsafe
filter override: command and protected-content checks always apply.

Use a private local archive directory. POSIX stores must be owned by the current
user with no group/other access. Windows ACLs are not managed by this package.
Symlinks, junctions, hard-linked archive files, UNC paths, and unsupported drive
aliases are not accepted. Unavailable or unsafe archives cause unchanged output,
not a reduction without recoverable evidence. See `docs/SECURITY-STATUS.md`.

## Observational hooks

`integrations/copilot-post-tool-use.json` remains a template, not an installer.
`integrations/windows-post-tool-use-hook.template.ps1` invokes the same Python
hook on Windows. Set its `-Python` parameter to the installed Python executable
and `-RawStore` to a private local folder. Run it as a separate PowerShell process.
Neither template rewrites context, approves tools, or blocks tools. They emit
diagnostic JSON only. Host registration and context replacement remain unverified;
no token or latency savings are claimed for the hooks.
The `integrations/` templates are repository-only resources; they are not
included in the Python wheel. Keep the checkout when using a template.

## Development

```bash
. .venv/bin/activate
pytest -q
python tests/smoke.py
python -m compileall -q src integrations
```

Tests do not require an installed `agent-speed` command. For a source-only run,
install `pytest>=8`, then use `PYTHONPATH=src python -m pytest -q` on POSIX, or
`$env:PYTHONPATH = "$PWD\src"; python -m pytest -q` in PowerShell.

GitHub Actions defines Linux/Windows jobs for Python 3.10 and 3.14, including
Windows PowerShell and PowerShell 7 subprocess checks. A separate wheel smoke
run uses the installed console and module entry points outside the source tree.

## Release notes

**0.1.2:** controlled CLI input errors; a working module entry point;
source-only subprocess tests; removal of `--unsafe-filter` and the Python
`unsafe` argument; explicit repository-only hook packaging; cross-platform CI;
blank-line separation regressions; descriptor-based POSIX archive access and
locked, validated Windows handles for both storage and retrieval.

**0.1.1:** replaced permissive command prefixes with an exact, case-sensitive
allowlist. Unknown options, shell composition, mutation commands, and full
patch output pass through unchanged. Repeated-line reduction preserves complete
line content and final-newline state. UTF-8 and binary archive I/O fix Windows
and CRLF recovery. Added the observational Windows hook template.

## Roadmap

1. Add structured JSONL events and deterministic filters for tests, compilers, Git, and search.
2. Add quotas, retention, and session isolation for raw archives.
3. Benchmark redacted Scout/Copilot traces.
4. Add SemIf/NanoJev adapters in shadow mode only.
5. Verify the Copilot hook contract on Linux, Windows ARM64, and macOS ARM64.
6. Publish after the release gate passes.
