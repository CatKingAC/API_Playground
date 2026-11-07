#!/usr/bin/env python3
"""EMPTY_ARTIFACT_FAKE_OK v0.1

Peer evidence (xiaoyou的dsh / DeepSeek-Harness, EigenFlux PM hb0527):
  Seven-column schema field-lock + dual negctrl for empty-artifact false-green:
    fixture_id / input_pair / expected_verdict / reason_code /
    must_not_trip / expected_artifact_digest_kind / fixture_version.
  Positive: rc=0 + len=0 claimed OK while a sibling run has rc=0 + len>floor
    → must RED EMPTY_ARTIFACT_FAKE_OK (not PASS).
  Negctrl.a: rc=0 + len>0 legal content → GREEN, must_not_trip.
  Negctrl.b: rc≠0 + len>0 ordinary failure → GREEN for this code
    (must not classify every nonzero exit as fake-green).
  Sibling fifth class PARTIAL_OK_TRUNCATED: rc=0, len>0, parseable, but
    actual_count < declared_count → RED (UNCONSUMABLE if count absent),
    never PASS. Same denominator-side assert family.

Arms:
  1. EMPTY_ARTIFACT_FAKE_OK — empty+rc0 claimed OK → FAIL
  2. EMPTY_ARTIFACT_HONEST — empty+rc0 recorded EMPTY_ARTIFACT → PASS
  3. NONEMPTY_OK_NEGCTRL — rc0+len>floor legal → PASS (must_not_trip)
  4. NONEMPTY_FAIL_NEGCTRL — rc≠0+len>0 ordinary fail → PASS (must_not_trip)
  5. PARTIAL_OK_TRUNCATED — actual_count < declared_count claimed OK → FAIL
  6. PARTIAL_OK_HONEST — short count recorded PARTIAL_OK_TRUNCATED → PASS
  7. PARTIAL_COUNT_ABSENT — declared missing → UNCONSUMABLE not PASS
  8. FULL_COUNT_OK — actual==declared → PASS (positive control)

analyze_only. Stdlib only.
Credit: xiaoyou的dsh (seven-col schema + dual negctrl + PARTIAL_OK_TRUNCATED);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any

FLOOR = 1


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")
    rc = receipt.get("rc")
    length = receipt.get("len")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state") or receipt.get("reason_code")
    declared = receipt.get("declared_count")
    actual = receipt.get("actual_count")

    # Arms 5/6/7/8 — partial / count
    if kind in (
        "partial_trunc_false_ok",
        "partial_trunc_honest",
        "partial_count_absent",
        "full_count_ok",
    ) or declared is not None or actual is not None or kind == "partial":
        if declared is None and kind == "partial_count_absent":
            if claimed_ok or recorded in ("PASS", "OK", "ACCEPTED"):
                return {
                    "judge": "FAIL",
                    "reason_code": "UNCONSUMABLE",
                    "detail": {"note": "missing declared_count cannot PASS"},
                }
            if recorded == "UNCONSUMABLE":
                return {
                    "judge": "PASS",
                    "reason_code": "UNCONSUMABLE",
                    "detail": {"honest": True},
                }
            return {
                "judge": "FAIL",
                "reason_code": "UNCONSUMABLE",
                "detail": {"recorded": recorded},
            }
        if isinstance(declared, int) and isinstance(actual, int):
            if actual < declared and claimed_ok and recorded != "PARTIAL_OK_TRUNCATED":
                return {
                    "judge": "FAIL",
                    "reason_code": "PARTIAL_OK_TRUNCATED",
                    "detail": {"declared": declared, "actual": actual},
                }
            if (
                actual < declared
                and recorded == "PARTIAL_OK_TRUNCATED"
                and not claimed_ok
            ):
                return {
                    "judge": "PASS",
                    "reason_code": "PARTIAL_OK_TRUNCATED",
                    "detail": {"honest": True, "declared": declared, "actual": actual},
                }
            if actual == declared and (claimed_ok or recorded in ("OK", "PASS", "ACCEPTED")):
                return {
                    "judge": "PASS",
                    "reason_code": "FULL_COUNT_OK",
                    "detail": {"declared": declared, "actual": actual},
                }

    # Arms 1/2 — empty artifact fake ok
    if kind in ("empty_fake_ok", "empty_honest") or (
        rc == 0 and isinstance(length, int) and length == 0
    ):
        if rc == 0 and length == 0 and claimed_ok and recorded not in (
            "EMPTY_ARTIFACT",
            "EMPTY_ARTIFACT_FAKE_OK",
        ):
            return {
                "judge": "FAIL",
                "reason_code": "EMPTY_ARTIFACT_FAKE_OK",
                "detail": {"rc": rc, "len": length},
            }
        if (
            rc == 0
            and length == 0
            and not claimed_ok
            and recorded in ("EMPTY_ARTIFACT", "EMPTY_ARTIFACT_FAKE_OK")
        ):
            return {
                "judge": "PASS",
                "reason_code": "EMPTY_ARTIFACT_FAKE_OK",
                "detail": {"honest": True},
            }

    # Arm 3 — nonempty legal negctrl
    if kind == "nonempty_ok" or (
        rc == 0 and isinstance(length, int) and length >= FLOOR and claimed_ok
        and receipt.get("content_legal") is True
    ):
        tripped = receipt.get("tripped_codes") or []
        if "EMPTY_ARTIFACT_FAKE_OK" in tripped:
            return {
                "judge": "FAIL",
                "reason_code": "EMPTY_ARTIFACT_FAKE_OK",
                "detail": {"note": "must_not_trip violated on legal nonempty"},
            }
        return {
            "judge": "PASS",
            "reason_code": "NONEMPTY_OK_NEGCTRL",
            "detail": {"rc": rc, "len": length},
        }

    # Arm 4 — ordinary nonzero exit negctrl
    if kind == "nonempty_fail" or (
        isinstance(rc, int)
        and rc != 0
        and isinstance(length, int)
        and length > 0
    ):
        tripped = receipt.get("tripped_codes") or []
        # Rough implementations that paint every nonzero as fake-green fail here
        if receipt.get("classified_as_fake_green") is True or (
            "EMPTY_ARTIFACT_FAKE_OK" in tripped
        ):
            return {
                "judge": "FAIL",
                "reason_code": "EMPTY_ARTIFACT_FAKE_OK",
                "detail": {"note": "ordinary fail must_not_trip EMPTY_ARTIFACT_FAKE_OK"},
            }
        return {
            "judge": "PASS",
            "reason_code": "NONEMPTY_FAIL_NEGCTRL",
            "detail": {"rc": rc, "len": length},
        }

    return {
        "judge": "FAIL",
        "reason_code": "UNDECIDABLE",
        "detail": {"kind": kind},
    }


FIXTURES = [
    {
        "case_id": "DSH-EMPTY-ARTIFACT-FAKE-OK-MUST-RED",
        "receipt": {
            "kind": "empty_fake_ok",
            "fixture_id": "green.empty.v1",
            "rc": 0,
            "len": 0,
            "claimed_ok": True,
            "reported_state": "OK",
            "expected_artifact_digest_kind": "content",
            "fixture_version": "v1",
        },
        "expect": "EMPTY_ARTIFACT_FAKE_OK",
    },
    {
        "case_id": "DSH-EMPTY-ARTIFACT-HONEST",
        "receipt": {
            "kind": "empty_honest",
            "fixture_id": "green.empty.v1.honest",
            "rc": 0,
            "len": 0,
            "claimed_ok": False,
            "recorded_state": "EMPTY_ARTIFACT",
            "fixture_version": "v1",
        },
        "expect": "EMPTY_ARTIFACT_FAKE_OK",
    },
    {
        "case_id": "DSH-EMPTY-NEGCTRL-NONEMPTY-OK",
        "receipt": {
            "kind": "nonempty_ok",
            "fixture_id": "green.empty.v1.neg.a",
            "rc": 0,
            "len": 32,
            "claimed_ok": True,
            "content_legal": True,
            "tripped_codes": [],
            "must_not_trip": ["EMPTY_ARTIFACT_FAKE_OK"],
            "fixture_version": "v1",
        },
        "expect": "NONEMPTY_OK_NEGCTRL",
    },
    {
        "case_id": "DSH-EMPTY-NEGCTRL-ORDINARY-FAIL",
        "receipt": {
            "kind": "nonempty_fail",
            "fixture_id": "green.empty.v1.neg.b",
            "rc": 2,
            "len": 16,
            "claimed_ok": False,
            "classified_as_fake_green": False,
            "tripped_codes": [],
            "must_not_trip": ["EMPTY_ARTIFACT_FAKE_OK"],
            "fixture_version": "v1",
        },
        "expect": "NONEMPTY_FAIL_NEGCTRL",
    },
    {
        "case_id": "DSH-PARTIAL-OK-TRUNCATED-MUST-RED",
        "receipt": {
            "kind": "partial_trunc_false_ok",
            "fixture_id": "partial.ok.trunc.v1",
            "rc": 0,
            "len": 48,
            "declared_count": 5,
            "actual_count": 3,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "PARTIAL_OK_TRUNCATED",
    },
    {
        "case_id": "DSH-PARTIAL-OK-TRUNCATED-HONEST",
        "receipt": {
            "kind": "partial_trunc_honest",
            "fixture_id": "partial.ok.trunc.v1.honest",
            "rc": 0,
            "len": 48,
            "declared_count": 5,
            "actual_count": 3,
            "claimed_ok": False,
            "recorded_state": "PARTIAL_OK_TRUNCATED",
            "fixture_version": "v1",
        },
        "expect": "PARTIAL_OK_TRUNCATED",
    },
    {
        "case_id": "DSH-PARTIAL-COUNT-ABSENT-UNCONSUMABLE",
        "receipt": {
            "kind": "partial_count_absent",
            "fixture_id": "partial.count.absent.v1",
            "rc": 0,
            "len": 48,
            "declared_count": None,
            "actual_count": 3,
            "claimed_ok": False,
            "recorded_state": "UNCONSUMABLE",
            "fixture_version": "v1",
        },
        "expect": "UNCONSUMABLE",
    },
    {
        "case_id": "DSH-FULL-COUNT-OK",
        "receipt": {
            "kind": "full_count_ok",
            "fixture_id": "full.count.ok.v1",
            "rc": 0,
            "len": 64,
            "declared_count": 4,
            "actual_count": 4,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "FULL_COUNT_OK",
    },
]


def main() -> int:
    rows = []
    ok = True
    for fx in FIXTURES:
        got = judge(fx["receipt"])
        match = got.get("reason_code") == fx["expect"]
        ok = ok and match
        rows.append(
            {
                "case_id": fx["case_id"],
                "expect": fx["expect"],
                "got": got.get("reason_code"),
                "match": match,
                "judge": got,
            }
        )
    out = {
        "version": "EMPTY_ARTIFACT_FAKE_OK/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "xiaoyou的dsh (seven-col schema + dual negctrl + PARTIAL_OK_TRUNCATED)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
