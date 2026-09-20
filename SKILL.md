---
name: agent-speed-layer
description: Use when accelerating Scout or GitHub Copilot with safe local tool-output reduction. Preserve raw evidence, avoid paid Jev, and fall back to the original workflow.
version: 0.1.0
author: Agent Speed Layer contributors
license: MIT
metadata:
  hermes:
    tags: [copilot, scout, latency, local, privacy, tool-output]
    related_skills: []
---

# Agent Speed Layer

Use the `agent-speed` CLI as a reversible, deterministic pre-processing layer beside Scout or GitHub Copilot. It does not replace the coding model and does not make permission decisions.

## Safe default

Filter only recognised read-only command output. Store the original output locally before any reduction. Return the original output when the command is unknown, the content contains error or security markers, or reduction is not clearly safe.

```bash
printf '%s' "$TOOL_OUTPUT" | agent-speed filter --command 'git status --short'
agent-speed retrieve --store ~/.agent-speed-layer/raw --id SHA256_ID
```

## Integration rule

Keep the first release observational. Do not install a Copilot hook that rewrites context until the exact host hook output contract is tested on the installed Copilot version. Use the provided hook template for logging and shadow measurement only.

## Model backends

Do not require a hosted Jev key. A future SemIf or NanoJev adapter may run in shadow mode, but it must not control tools until a labelled workload shows acceptable agreement, latency, false omission rate, and recovery behavior.

## Never filter

- credentials, tokens, private keys, or personal data;
- tracebacks, errors, failed tests, security output, or exact command evidence;
- source code, patches, diffs, or outputs needed to reproduce a result;
- any command that mutates state.

## Verification

Run the package tests and a smoke test. Confirm the raw identifier retrieves byte-for-byte original output. Keep the raw archive local and outside a repository.
