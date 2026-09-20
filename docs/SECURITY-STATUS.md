# Agent Speed Layer — MVP security status

The first MVP remains deterministic, local, and observational. It does not install Copilot hooks automatically and it does not include model or hosted Jev dependencies.

## Implemented controls

- Input size limit: 4 MiB.
- Shell metacharacters fail closed.
- POSIX creation requests mode 0700 for directories and 0600 for files. Existing stores and files must be owned by the current user and have no group/other permission bits; unsafe permissions are rejected, not changed.
- POSIX access walks directory descriptors with no-follow opens. Archive creation, validation, reading, and writing stay anchored to opened descriptors.
- Windows access holds directory handles with read access and read-only sharing, rejecting reparse points and blocking concurrent rename or reparse writers. Subsequent opens use the volume-GUID anchor, not a mutable drive letter.
- Windows supports local volume paths only. UNC/device paths, subdirectory drive aliases, junctions, and symlinked archive paths are rejected.
- Windows ACLs remain a caller responsibility: use private file ACLs and private inheritable directory ACLs. The package does not audit or rewrite existing ACLs; no Windows confidentiality guarantee is inferred from POSIX mode bits. Windows `mkdir(0700)` has additional protection only on Python 3.13 and newer.
- Archive leaves must be regular single-link files. Reads and writes use the validated handle; retrieval checks the digest before emitting content. No pathname chmod is used.
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

## Threat boundary

These controls prevent path substitution from redirecting archive operations
through symlinks, junctions, or hard-linked files in the normalized absolute path.
Normalization removes `.` and `..` before traversal. The parent location must
already be trusted and private, particularly when creating new directories on
Windows. Sharing violations and unsupported paths fail closed: the filter
returns the original text without reduction, while retrieval reports an error.

This is not isolation from another process running as the same user, an
administrator, or a process that can change the user's ACLs. Such actors can
already access the user's data or remove archives. On POSIX, a renamed directory
remains the same opened object; later pathname-based recovery may become
unavailable. Quotas, retention, and authenticated retrieval remain out of scope.
