# Agent Speed Layer — MVP security status

The first MVP remains deterministic, local, and observational. It does not install Copilot hooks automatically and it does not include model or hosted Jev dependencies.

## Implemented controls

- Input size limit: 4 MiB.
- Shell metacharacters fail closed.
- Archive directories use mode 0700.
- Archive files use mode 0600.
- Archive writes reject symlink targets.
- Raw paths are not emitted in JSON consumed by hooks.
- Malformed Copilot hook events return safely without replacement output.
- Unknown, mutating, protected, or oversized inputs remain unchanged.
- Exact raw retrieval remains available through the local CLI.

## Not yet implemented

- Archive quotas and retention.
- Session isolation and authenticated retrieval.
- Full secret-pattern detection.
- Structured JSONL event protocol.
- Native SemIf or NanoJev provider.
- Verified Copilot context-replacement contract.

Do not enable automatic Copilot context replacement until those missing controls and the host-specific hook contract are tested.
