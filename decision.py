"""POLICY-2 (approved 5 November 2026) launch-readiness evaluator.

evaluate(row) → {status, reason, policy_id, source_id, snapshot, execution}

Rules (field-value driven; never hardcoded feature IDs):
  1. BLOCKED  — blockers > 0  OR  security is False  OR  rollback is False.
               Known failure wins even when another field is null/missing.
  2. UNKNOWN  — any of blockers / security / rollback is null / missing.
  3. READY    — blockers == 0  AND  security is True  AND  rollback is True.

Invalid input (blockers not a nonneg-int-or-None, security/rollback not bool-or-None)
raises ValueError so callers can show an error state.
"""


def _validate(row: dict) -> None:
    """Raise ValueError for out-of-contract field values."""
    blockers = row.get("blockers")
    if blockers is not None:
        if not isinstance(blockers, int) or isinstance(blockers, bool) or blockers < 0:
            raise ValueError(
                f"blockers must be a non-negative integer or null, got {blockers!r}"
            )

    for field in ("security", "rollback"):
        val = row.get(field)
        if val is not None and not isinstance(val, bool):
            raise ValueError(
                f"{field} must be true, false, or null, got {val!r}"
            )


def evaluate(row: dict) -> dict:
    """Evaluate a single feature row against POLICY-2."""
    _validate(row)

    blockers = row.get("blockers")
    security = row.get("security")
    rollback = row.get("rollback")

    source_id = row.get("source")
    snapshot = row.get("snapshot")

    # --- Rule 1: BLOCKED — known failure wins over any missing evidence ---
    blocked_reasons = []
    if isinstance(blockers, int) and blockers > 0:
        blocked_reasons.append(f"{blockers} open blocker(s)")
    if security is False:
        blocked_reasons.append("security check failed")
    if rollback is False:
        blocked_reasons.append("rollback not verified")

    if blocked_reasons:
        return {
            "status": "BLOCKED",
            "reason": "Blocked: " + "; ".join(blocked_reasons) + ".",
            "policy_id": "POLICY-2",
            "source_id": source_id,
            "snapshot": snapshot,
            "execution": "none",
        }

    # --- Rule 2: UNKNOWN — any required field null / missing ---
    unknown_reasons = []
    if blockers is None:
        unknown_reasons.append("blocker count not reported")
    if security is None:
        unknown_reasons.append("security status unknown")
    if rollback is None:
        unknown_reasons.append("rollback status unknown")

    if unknown_reasons:
        return {
            "status": "UNKNOWN",
            "reason": "Incomplete evidence: " + "; ".join(unknown_reasons) + ".",
            "policy_id": "POLICY-2",
            "source_id": source_id,
            "snapshot": snapshot,
            "execution": "none",
        }

    # --- Rule 3: READY ---
    return {
        "status": "READY",
        "reason": "All checks passed: zero blockers, security verified, rollback verified.",
        "policy_id": "POLICY-2",
        "source_id": source_id,
        "snapshot": snapshot,
        "execution": "none",
    }
