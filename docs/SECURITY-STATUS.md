# Agent Speed Layer — MVP security status

The first MVP remains deterministic, local, and observational. It does not install Copilot hooks automatically and it does not include model or hosted Jev dependencies.

## Implemented controls

- Input size limit: 4 MiB.
- Shell metacharacters fail closed.
- POSIX archive directories use mode 0700 and archive files use mode 0600.
- On Windows, POSIX mode bits are not an access-control guarantee; Windows ACL validation remains pending.
- Archive writes reject symlink targets.
- Raw paths are not emitted in JSON consumed by hooks.
- Malformed Copilot hook events return safely without replacement output.
- Unknown, mutating, protected, or oversized inputs remain unchanged.
- Exact raw retrieval reads bytes and preserves LF and CRLF content byte-for-byte.
- Windows PowerShell hook template is provided for review only; it is not registered or installed.

## Not yet implemented

- Archive quotas and retention.
- Session isolation and authenticated retrieval.
- Full secret-pattern detection.
- Structured JSONL event protocol.
- Native SemIf or NanoJev provider.
- Verified Copilot context-replacement contract.

Do not enable automatic Copilot context replacement until those missing controls and the host-specific hook contract are tested.
