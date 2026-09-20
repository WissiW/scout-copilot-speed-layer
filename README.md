# Agent Speed Layer

A local, open-source sidecar for Scout and GitHub Copilot CLI. It reduces repetitive tool output before it reaches an agent while preserving the raw result for recovery.

## Current release: deterministic MVP

The MVP is deliberately narrow and safe:

- No Jev, API key, model, daemon, or network dependency.
- Deterministic repeated-line reduction for selected read-only commands.
- Original output is stored locally before reduction.
- Retrieval verifies the SHA-256 content identifier.
- Unknown commands, mutation, errors, security markers, and oversized input pass through unchanged.
- Copilot integration is observational only. It does not rewrite context, approve tools, or block tools.

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

## Use

```bash
printf '%s' "$TOOL_OUTPUT" | agent-speed filter --command 'git status --short'
agent-speed retrieve --store ~/.agent-speed-layer/raw --id SHA256_ID
```

The filter emits JSON with `text`, `changed`, `raw_id`, and `reason`. The filesystem path is intentionally not emitted.

## Evidence-gated completion

The optional evidence core is pure Python and has no dependencies. It prevents an agent's `done` statement from becoming completion status. Only matching observed state plus independent evidence can return `verified`.

```python
from agent_speed.evidence import verify_completion

decision = verify_completion(
    required={"tests": "pass"},
    observed={"tests": "pass"},
    evidence=[{"kind": "test", "result": True, "id": "tests-123"}],
    attempts=1,
    max_attempts=3,
)
```

Statuses are `verified`, `needs_verification`, `needs_repair`, or `bounded_failure`. This layer does not execute repairs, approve tools, or create a daemon. A caller owns execution and must enforce its own time, token, cost, and permission budgets.


`integrations/copilot-post-tool-use.json` is a reviewed template, not an automatic installer. The hook remains observational until its exact output contract is verified against the installed Copilot CLI version.

## Development

```bash
. .venv/bin/activate
pytest -q
python tests/smoke.py
python -m compileall -q src integrations
```

## Roadmap

1. Add structured JSONL events and deterministic filters for tests, compilers, Git, and search.
2. Add quotas, retention, and session isolation for raw archives.
3. Benchmark redacted Scout/Copilot traces.
4. Add SemIf/NanoJev adapters in shadow mode only.
5. Verify the Copilot hook contract on Linux, Windows ARM64, and macOS ARM64.
6. Publish after the release gate passes.
