from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceDecision:
    status: str
    reason: str
    evidence_ids: tuple[str, ...]
    attempts: int


def evidence_id(kind: str, value: Any) -> str:
    payload = json.dumps({"kind": kind, "value": value}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def verify_completion(
    *,
    required: dict[str, Any],
    observed: dict[str, Any],
    evidence: list[dict[str, Any]],
    attempts: int,
    max_attempts: int = 3,
) -> EvidenceDecision:
    """Allow completion only when independent observed evidence matches requirements."""
    if attempts >= max_attempts and required != observed:
        return EvidenceDecision("bounded_failure", "attempt budget exhausted", (), attempts)
    if required != observed:
        return EvidenceDecision("needs_repair", "observed state does not match requirements", (), attempts)
    valid: list[str] = []
    for item in evidence:
        if not isinstance(item, dict) or item.get("kind") not in {"test", "assertion", "readback"}:
            continue
        if item.get("result") is not True:
            continue
        valid.append(str(item.get("id") or evidence_id(str(item["kind"]), item.get("value"))))
    if not valid:
        return EvidenceDecision("needs_verification", "matching state has no independent evidence", (), attempts)
    return EvidenceDecision("verified", "requirements match independently verified evidence", tuple(valid), attempts)


def decision_json(decision: EvidenceDecision) -> str:
    return json.dumps({
        "status": decision.status,
        "reason": decision.reason,
        "evidence_ids": list(decision.evidence_ids),
        "attempts": decision.attempts,
    }, sort_keys=True)
