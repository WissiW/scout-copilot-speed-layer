# MVP limitations

This first release is deliberately narrow.

- Only complete identical lines are reduced, including their whitespace and terminators. Different line endings are not merged, and the final-newline state is preserved.
- Command classification validates complete supported command arguments and fails closed for shell composition or mutating commands.
- Full `git diff` remains unchanged; only `git diff --stat` is eligible for reduction.
- Raw retrieval is byte-exact and verifies the SHA-256 identifier over stored bytes.
- The Copilot hook is observational. Copilot post-tool hooks do not automatically replace the model context. A future integration must use a verified `additionalContext` or supported host extension contract.
- The model backend is not included. This keeps installation offline, free, and license-clean.
- On POSIX, raw content uses restrictive directory and file modes. Windows ACLs are inherited from the archive location; the package does not configure or audit them. Choose a private directory. POSIX mode checks do not prove Windows privacy.
- Archive access rejects symlink/junction paths, hard-linked files, and unsafe POSIX ownership or permissions. Windows requires a local volume path, not a UNC/device path or subdirectory drive alias. File-sharing conflicts fail closed.
- The package cannot protect archives from the same user or an administrator. A removed or renamed store can make later recovery unavailable.
- The project has no hosted service, telemetry, API key, or paid Jev dependency.
