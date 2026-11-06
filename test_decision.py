"""Extra tests for decision.evaluate() — separate from check.py (which is frozen).

Run with:
    python3 test_decision.py
    python3 -m unittest test_decision

Covers:
    Task 1  — unittest-based unit tests (TestBlocked, TestBlockedPrecedence,
              TestUnknown, TestReady, TestFieldValueDriven, TestInputValidation,
              TestMetadata)
    Task 2  — property-based tests using random-seeded loops (TestProperties)

These tests NEVER import from or touch check.py, frozen.sha256.json,
data/, quick_upload/, or updates/.
"""

import random
import unittest

from decision import evaluate


# ── Shared helper ─────────────────────────────────────────────────────────────

def _row(blockers, security, rollback, *, id_="X000", feature="Widget",
         owner="Tester", source="QA-X000", snapshot="SNAPSHOT-TEST"):
    """Build a minimal Feature Row dict."""
    return {
        "id": id_,
        "feature": feature,
        "owner": owner,
        "blockers": blockers,
        "security": security,
        "rollback": rollback,
        "source": source,
        "snapshot": snapshot,
    }


# ── Task 1.1 ─────────────────────────────────────────────────────────────────


class TestBlocked(unittest.TestCase):
    """Each blocking condition in isolation."""

    def test_blockers_greater_than_zero(self):
        r = evaluate(_row(1, True, True))
        self.assertEqual(r["status"], "BLOCKED")

    def test_security_false(self):
        r = evaluate(_row(0, False, True))
        self.assertEqual(r["status"], "BLOCKED")

    def test_rollback_false(self):
        r = evaluate(_row(0, True, False))
        self.assertEqual(r["status"], "BLOCKED")

    def test_multiple_blockers(self):
        r = evaluate(_row(3, True, True))
        self.assertEqual(r["status"], "BLOCKED")

    def test_all_three_failing(self):
        r = evaluate(_row(2, False, False))
        self.assertEqual(r["status"], "BLOCKED")


# ── Task 1.2 ─────────────────────────────────────────────────────────────────


class TestBlockedPrecedence(unittest.TestCase):
    """Known failure wins even when another field is null (BLOCKED, not UNKNOWN).

    This is the core POLICY-2 rule: a known bad value takes priority over
    missing evidence.  blockers=None means 'we don't know the count', but
    rollback=False is a definite failure — so the result is BLOCKED.
    """

    def test_null_blockers_plus_rollback_false(self):
        # ← explicit requirement: blockers=None AND rollback=False → BLOCKED
        r = evaluate(_row(None, True, False))
        self.assertEqual(r["status"], "BLOCKED",
                         "Known failure (rollback=False) must win over null blockers")

    def test_null_blockers_plus_security_false(self):
        r = evaluate(_row(None, False, True))
        self.assertEqual(r["status"], "BLOCKED")

    def test_blockers_positive_plus_security_null(self):
        r = evaluate(_row(2, None, True))
        self.assertEqual(r["status"], "BLOCKED")

    def test_zero_blockers_security_null_rollback_false(self):
        r = evaluate(_row(0, None, False))
        self.assertEqual(r["status"], "BLOCKED")

    def test_all_three_null_except_one_failure(self):
        # security=False plus everything else null
        r = evaluate(_row(None, False, None))
        self.assertEqual(r["status"], "BLOCKED")


# ── Task 1.3 ─────────────────────────────────────────────────────────────────


class TestUnknown(unittest.TestCase):
    """Null fields with no failures present → UNKNOWN."""

    def test_blockers_null(self):
        r = evaluate(_row(None, True, True))
        self.assertEqual(r["status"], "UNKNOWN")

    def test_security_null(self):
        r = evaluate(_row(0, None, True))
        self.assertEqual(r["status"], "UNKNOWN")

    def test_rollback_null(self):
        r = evaluate(_row(0, True, None))
        self.assertEqual(r["status"], "UNKNOWN")

    def test_all_three_null(self):
        r = evaluate(_row(None, None, None))
        self.assertEqual(r["status"], "UNKNOWN")

    def test_blockers_zero_security_null_rollback_null(self):
        r = evaluate(_row(0, None, None))
        self.assertEqual(r["status"], "UNKNOWN")


# ── Task 1.4 ─────────────────────────────────────────────────────────────────


class TestReady(unittest.TestCase):
    """All checks passing → READY, regardless of identity fields."""

    def test_standard_row(self):
        r = evaluate(_row(0, True, True))
        self.assertEqual(r["status"], "READY")

    def test_different_owner_and_source(self):
        r = evaluate(_row(0, True, True, id_="L101", feature="Search",
                          owner="Asha", source="QA-101", snapshot="SNAPSHOT-A"))
        self.assertEqual(r["status"], "READY")

    def test_different_snapshot(self):
        r = evaluate(_row(0, True, True, snapshot="SNAPSHOT-B"))
        self.assertEqual(r["status"], "READY")


# ── Task 1.5 ─────────────────────────────────────────────────────────────────


class TestFieldValueDriven(unittest.TestCase):
    """Evaluation is driven entirely by field values, never by ID lookup."""

    def test_unseen_id_all_clear_returns_ready(self):
        # ← explicit requirement: unseen feature ID with valid fields evaluates normally
        r = evaluate(_row(0, True, True, id_="ZZZZ-9999",
                          feature="Brand new feature no one has seen",
                          owner="Ghost", source="QA-ZZZZ-9999",
                          snapshot="SNAPSHOT-EXTRA"))
        self.assertEqual(r["status"], "READY",
                         "Unseen feature ID must be evaluated by field values, not ID lookup")

    def test_unseen_id_with_blocker_returns_blocked(self):
        r = evaluate(_row(2, True, True, id_="ZZZZ-9998"))
        self.assertEqual(r["status"], "BLOCKED")

    def test_two_rows_same_fields_different_id_same_status(self):
        row_a = _row(0, True, True, id_="AAA-001", owner="Alice")
        row_b = _row(0, True, True, id_="BBB-999", owner="Bob")
        self.assertEqual(evaluate(row_a)["status"], evaluate(row_b)["status"])

    def test_two_rows_same_fields_different_id_blocked(self):
        row_a = _row(1, True, True, id_="AAA-001")
        row_b = _row(1, True, True, id_="ZZZ-999")
        self.assertEqual(evaluate(row_a)["status"], evaluate(row_b)["status"])


# ── Task 1.6 ─────────────────────────────────────────────────────────────────


class TestInputValidation(unittest.TestCase):
    """Invalid field types must raise ValueError — never silently proceed."""

    def test_negative_blockers(self):
        with self.assertRaises(ValueError):
            evaluate(_row(-1, True, True))

    def test_string_blockers(self):
        with self.assertRaises(ValueError):
            evaluate(_row("1", True, True))

    def test_float_blockers(self):
        with self.assertRaises(ValueError):
            evaluate(_row(1.5, True, True))

    def test_bool_as_blockers_true(self):
        # bool is a subclass of int in Python, but the contract excludes it
        with self.assertRaises(ValueError):
            evaluate(_row(True, True, True))

    def test_bool_as_blockers_false(self):
        with self.assertRaises(ValueError):
            evaluate(_row(False, True, True))

    def test_string_security(self):
        with self.assertRaises(ValueError):
            evaluate(_row(0, "true", True))

    def test_string_rollback(self):
        with self.assertRaises(ValueError):
            evaluate(_row(0, True, "false"))

    def test_integer_security(self):
        with self.assertRaises(ValueError):
            evaluate(_row(0, 1, True))

    def test_integer_rollback(self):
        with self.assertRaises(ValueError):
            evaluate(_row(0, True, 0))


# ── Task 1.7 ─────────────────────────────────────────────────────────────────


class TestMetadata(unittest.TestCase):
    """Every result carries the correct six-key contract regardless of status."""

    def _assert_metadata(self, row):
        r = evaluate(row)
        self.assertEqual(r["policy_id"], "POLICY-2")
        self.assertEqual(r["source_id"], row["source"])
        self.assertEqual(r["snapshot"], row["snapshot"])
        self.assertEqual(r["execution"], "none")
        self.assertIsInstance(r["reason"], str)
        self.assertTrue(r["reason"].strip(), "reason must be non-empty")
        self.assertIn(r["status"], {"READY", "BLOCKED", "UNKNOWN"})

    def test_metadata_ready(self):
        self._assert_metadata(_row(0, True, True,
                                   source="QA-M001", snapshot="SNAPSHOT-META"))

    def test_metadata_blocked(self):
        self._assert_metadata(_row(3, True, True,
                                   source="QA-M002", snapshot="SNAPSHOT-META"))

    def test_metadata_unknown(self):
        self._assert_metadata(_row(None, True, True,
                                   source="QA-M003", snapshot="SNAPSHOT-META"))

    def test_source_and_snapshot_passed_through(self):
        row = _row(0, True, True, source="QA-SPECIAL-42",
                   snapshot="SNAPSHOT-SPECIAL")
        r = evaluate(row)
        self.assertEqual(r["source_id"], "QA-SPECIAL-42")
        self.assertEqual(r["snapshot"], "SNAPSHOT-SPECIAL")


# ── Task 2: Property-based tests ─────────────────────────────────────────────


def _rand_nonneg_int_or_none(rng):
    """Return a non-negative int (0–5) or None."""
    v = rng.randint(0, 6)
    return None if v == 6 else v


def _rand_bool_or_none(rng):
    """Return True, False, or None."""
    v = rng.randint(0, 2)
    return [True, False, None][v]


def _rand_id(rng):
    return f"ID-{rng.randint(1000, 9999)}"


def _rand_valid_row(rng):
    """Generate any valid Feature Row (will not raise ValueError)."""
    return _row(
        _rand_nonneg_int_or_none(rng),
        _rand_bool_or_none(rng),
        _rand_bool_or_none(rng),
        id_=_rand_id(rng),
        owner=f"Owner-{rng.randint(1, 99)}",
        source=f"QA-{rng.randint(100, 999)}",
        snapshot=f"SNAPSHOT-{rng.choice(['A', 'B', 'C'])}",
    )


def _is_blocked(row):
    b, s, r = row["blockers"], row["security"], row["rollback"]
    return (isinstance(b, int) and not isinstance(b, bool) and b > 0) \
           or s is False or r is False


def _has_missing(row):
    return (row["blockers"] is None
            or row["security"] is None
            or row["rollback"] is None)


ITERATIONS = 200


class TestProperties(unittest.TestCase):
    """Property-based tests: universal invariants checked over random inputs.

    Each test uses random.seed(42) for reproducibility.  Every iteration
    generates a new random row and asserts the invariant holds.
    """

    # P1 ── Known Failure Blocks Unconditionally

    def test_p1_known_failure_always_blocked(self):
        """Any row with at least one known failure must be BLOCKED."""
        rng = random.Random(42)
        options = ["blockers", "security", "rollback"]
        for i in range(ITERATIONS):
            row = _rand_valid_row(rng)
            # Force at least one known failure
            which = rng.choice(options)
            if which == "blockers":
                row["blockers"] = rng.randint(1, 10)
            elif which == "security":
                row["security"] = False
            else:
                row["rollback"] = False
            # The other two fields may be anything valid (includes None)
            r = evaluate(row)
            self.assertEqual(r["status"], "BLOCKED",
                             f"Iteration {i}: expected BLOCKED for row={row}, got {r}")

    # P2 ── Missing Evidence Without Known Failure Returns UNKNOWN

    def test_p2_missing_evidence_no_failure_is_unknown(self):
        """No known failure + at least one null field → UNKNOWN."""
        rng = random.Random(42)
        for i in range(ITERATIONS):
            # Start with a passing row, then null out at least one field
            blockers = rng.randint(0, 5)
            security = True
            rollback = True
            # Pick ≥1 field to null (but don't introduce a known failure)
            null_candidates = rng.sample(["blockers", "security", "rollback"],
                                         k=rng.randint(1, 3))
            row = _row(blockers, security, rollback, source=f"QA-{i}", snapshot="SNAP")
            for field in null_candidates:
                row[field] = None
            # Guard: if we accidentally created a known failure, skip
            if _is_blocked(row):
                continue
            if not _has_missing(row):
                continue
            r = evaluate(row)
            self.assertEqual(r["status"], "UNKNOWN",
                             f"Iteration {i}: expected UNKNOWN for row={row}, got {r}")

    # P3 ── Complete Passing Evidence Returns READY

    def test_p3_all_passing_is_ready(self):
        """blockers=0, security=True, rollback=True → always READY."""
        rng = random.Random(42)
        for i in range(ITERATIONS):
            row = _row(0, True, True,
                       id_=_rand_id(rng),
                       owner=f"Owner-{i}",
                       source=f"QA-{i}",
                       snapshot=f"SNAPSHOT-{rng.choice(['A', 'B', 'C'])}")
            r = evaluate(row)
            self.assertEqual(r["status"], "READY",
                             f"Iteration {i}: expected READY for row={row}, got {r}")

    # P4 ── Field-Value-Driven Evaluation

    def test_p4_same_rule_fields_same_status(self):
        """Two rows that differ only in id/feature/owner must produce the same status."""
        rng = random.Random(42)
        for i in range(ITERATIONS):
            blockers = _rand_nonneg_int_or_none(rng)
            security = _rand_bool_or_none(rng)
            rollback = _rand_bool_or_none(rng)
            row_a = _row(blockers, security, rollback,
                         id_=f"AAA-{i}", owner="Alice", source="QA-A", snapshot="SNAP")
            row_b = _row(blockers, security, rollback,
                         id_=f"ZZZ-{i}", owner="Bob",   source="QA-B", snapshot="SNAP")
            self.assertEqual(evaluate(row_a)["status"], evaluate(row_b)["status"],
                             f"Iteration {i}: same rule fields must yield same status")

    # P5 ── Result Metadata Invariant

    def test_p5_metadata_always_correct(self):
        """Every valid row produces a result with all six keys correct."""
        rng = random.Random(42)
        for i in range(ITERATIONS):
            row = _rand_valid_row(rng)
            r = evaluate(row)
            self.assertEqual(r["policy_id"], "POLICY-2",
                             f"Iteration {i}: wrong policy_id")
            self.assertEqual(r["source_id"], row["source"],
                             f"Iteration {i}: wrong source_id")
            self.assertEqual(r["snapshot"], row["snapshot"],
                             f"Iteration {i}: wrong snapshot")
            self.assertEqual(r["execution"], "none",
                             f"Iteration {i}: execution must be 'none'")
            self.assertIsInstance(r["reason"], str,
                                  f"Iteration {i}: reason must be a str")
            self.assertTrue(r["reason"].strip(),
                            f"Iteration {i}: reason must be non-empty")
            self.assertIn(r["status"], {"READY", "BLOCKED", "UNKNOWN"},
                          f"Iteration {i}: invalid status {r['status']!r}")

    # P7 ── Blocked Reason Cites All Failures

    def test_p7_blocked_reason_cites_failures(self):
        """BLOCKED reason must mention every failing field present in the row."""
        rng = random.Random(42)
        for i in range(ITERATIONS):
            row = _rand_valid_row(rng)
            failing = []
            # Randomly impose ≥1 known failure
            if rng.random() < 0.5:
                row["blockers"] = rng.randint(1, 5)
                failing.append("blockers")
            if rng.random() < 0.5:
                row["security"] = False
                failing.append("security")
            if rng.random() < 0.5:
                row["rollback"] = False
                failing.append("rollback")
            if not failing:
                row["rollback"] = False
                failing.append("rollback")

            r = evaluate(row)
            self.assertEqual(r["status"], "BLOCKED",
                             f"Iteration {i}: expected BLOCKED, got {r['status']}")
            reason_lower = r["reason"].lower()
            if "blockers" in failing:
                self.assertTrue(
                    any(w in reason_lower for w in ("blocker", "open")),
                    f"Iteration {i}: reason should cite blockers. reason={r['reason']!r}")
            if "security" in failing:
                self.assertTrue(
                    "security" in reason_lower,
                    f"Iteration {i}: reason should cite security. reason={r['reason']!r}")
            if "rollback" in failing:
                self.assertTrue(
                    "rollback" in reason_lower,
                    f"Iteration {i}: reason should cite rollback. reason={r['reason']!r}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
