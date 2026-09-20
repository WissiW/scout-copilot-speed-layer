# Lightweight evidence core

This module adapts the evidence-gated architecture described in the referenced post without adding a model or service.

- Graph state remains the caller's responsibility.
- Completion is not accepted from an agent claim.
- Repair execution remains outside this package.
- Evidence must be a successful test, assertion, or readback.
- Attempts are bounded by the caller-supplied limit.
- Permissions and destructive-action policy remain deterministic and external.

The implementation uses only the Python standard library and adds no RAM-resident process, database, or network activity.
