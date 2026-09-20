from agent_speed.evidence import verify_completion


def test_done_without_evidence_is_not_verified() -> None:
    result = verify_completion(required={"tests": "pass"}, observed={"tests": "pass"}, evidence=[], attempts=1)
    assert result.status == "needs_verification"


def test_independent_readback_verifies() -> None:
    result = verify_completion(
        required={"tests": "pass"},
        observed={"tests": "pass"},
        evidence=[{"kind": "readback", "result": True, "id": "readback-1"}],
        attempts=1,
    )
    assert result.status == "verified"
    assert result.evidence_ids == ("readback-1",)


def test_mismatch_requests_repair() -> None:
    result = verify_completion(required={"tests": "pass"}, observed={"tests": "fail"}, evidence=[], attempts=1)
    assert result.status == "needs_repair"


def test_attempts_are_bounded() -> None:
    result = verify_completion(required={"x": 1}, observed={"x": 0}, evidence=[], attempts=3, max_attempts=3)
    assert result.status == "bounded_failure"
