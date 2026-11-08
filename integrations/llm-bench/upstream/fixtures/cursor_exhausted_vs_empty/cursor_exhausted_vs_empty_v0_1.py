#!/usr/bin/env python3
"""CURSOR_EXHAUSTED_VS_EMPTY v0.1

Peer evidence (rosa agent, EigenFlux PM hb0733/hb0756):
  Collapse "cursor exhausted" and "empty result" into one green is the
  false-green. A genuine empty page is EMPTY_ALLOWED. Two recompute
  probes MUST go red when the collapse is hiding something else:
    - cursor_advanced_without_item
    - receipt_missing
  must_not_trip is written as recompute-must-red, not as a success
  portrait (avoids a tautological constant-true assert).

Sibling RECEIPT_SCOPED_TO_RUN (same lock):
  A receipt is only valid under its originating run.
  expected_verdict = ACCEPTED_UNDER_RUN
  recompute-must-red probes:
    - receipt_from_other_run
    - run_id_reused

Arms (must-fail + control, paired):
  1. CURSOR_ADVANCE_WITHOUT_ITEM_MUST_RED — cursor advanced, 0 items,
     claimed EMPTY_ALLOWED, probes stayed green → FAIL
  2. CURSOR_ADVANCE_WITHOUT_ITEM_HONEST — same facts, recorded
     CURSOR_EXHAUSTED_VS_EMPTY, probe tripped → PASS
  3. RECEIPT_MISSING_MUST_RED — empty page, no receipt, claimed
     EMPTY_ALLOWED, probes stayed green → FAIL
  4. EMPTY_ALLOWED — genuine empty (no cursor advance, receipt present)
     → PASS EMPTY_ALLOWED
  5. RECEIPT_FROM_OTHER_RUN_MUST_RED — receipt_run_id != current_run_id,
     claimed ACCEPTED_UNDER_RUN, probes stayed green → FAIL
  6. RECEIPT_FROM_OTHER_RUN_HONEST — same facts, recorded
     RECEIPT_SCOPED_TO_RUN, probe tripped → PASS
  7. RUN_ID_REUSED_MUST_RED — same run_id reused across executions,
     claimed ACCEPTED_UNDER_RUN, probes stayed green → FAIL
  8. ACCEPTED_UNDER_RUN — same run, not reused → PASS ACCEPTED_UNDER_RUN

analyze_only. Stdlib only.
Credit: rosa agent (naming + expected_verdict/must_not_trip lock +
        recompute-must-red semantics); Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


CURSOR_PROBES = ("cursor_advanced_without_item", "receipt_missing")
RECEIPT_PROBES = ("receipt_from_other_run", "run_id_reused")


def cursor_probes(receipt: dict[str, Any]) -> dict[str, bool]:
    items = _as_int(receipt.get("items_returned"))
    advanced = receipt.get("cursor_advanced") is True
    return {
        "cursor_advanced_without_item": advanced and items == 0,
        "receipt_missing": receipt.get("has_receipt") is False,
    }


def receipt_probes(receipt: dict[str, Any]) -> dict[str, bool]:
    rec_run = receipt.get("receipt_run_id")
    cur_run = receipt.get("current_run_id")
    return {
        "receipt_from_other_run": (
            rec_run is not None and cur_run is not None and rec_run != cur_run
        ),
        "run_id_reused": receipt.get("run_id_reused") is True,
    }


def _hot(probes: dict[str, bool]) -> list[str]:
    return [name for name, flag in probes.items() if flag]


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state") or receipt.get("reason_code")
    claimed_verdict = receipt.get("claimed_verdict")
    tripped = list(receipt.get("tripped_codes") or [])

    cursor_kinds = {
        "cursor_advance_without_item",
        "cursor_advance_without_item_honest",
        "receipt_missing",
        "empty_allowed",
    }
    receipt_kinds = {
        "receipt_other_run",
        "receipt_other_run_honest",
        "run_id_reused",
        "accepted_under_run",
    }

    if kind in cursor_kinds or receipt.get("check") == "cursor_empty":
        hot = _hot(cursor_probes(receipt))
        missed = [name for name in hot if name not in tripped]
        if hot:
            hiding = claimed_ok or claimed_verdict == "EMPTY_ALLOWED"
            if hiding and (missed or recorded != "CURSOR_EXHAUSTED_VS_EMPTY"):
                return {
                    "judge": "FAIL",
                    "reason_code": "CURSOR_EXHAUSTED_VS_EMPTY",
                    "detail": {"hot_probes": hot, "missed": missed},
                }
            if (
                (not claimed_ok)
                and recorded == "CURSOR_EXHAUSTED_VS_EMPTY"
                and not missed
            ):
                return {
                    "judge": "PASS",
                    "reason_code": "CURSOR_EXHAUSTED_VS_EMPTY",
                    "detail": {"honest": True, "hot_probes": hot},
                }
            return {
                "judge": "FAIL",
                "reason_code": "CURSOR_EXHAUSTED_VS_EMPTY",
                "detail": {"hot_probes": hot, "missed": missed},
            }
        false_trips = [name for name in CURSOR_PROBES if name in tripped]
        if false_trips:
            return {
                "judge": "FAIL",
                "reason_code": "CURSOR_EXHAUSTED_VS_EMPTY",
                "detail": {"note": "probes must not fire on genuine empty", "false_trips": false_trips},
            }
        return {
            "judge": "PASS",
            "reason_code": "EMPTY_ALLOWED",
            "detail": {"items_returned": receipt.get("items_returned")},
        }

    if kind in receipt_kinds or receipt.get("check") == "receipt_scope":
        hot = _hot(receipt_probes(receipt))
        missed = [name for name in hot if name not in tripped]
        if hot:
            hiding = claimed_ok or claimed_verdict == "ACCEPTED_UNDER_RUN"
            if hiding and (missed or recorded != "RECEIPT_SCOPED_TO_RUN"):
                return {
                    "judge": "FAIL",
                    "reason_code": "RECEIPT_SCOPED_TO_RUN",
                    "detail": {"hot_probes": hot, "missed": missed},
                }
            if (
                (not claimed_ok)
                and recorded == "RECEIPT_SCOPED_TO_RUN"
                and not missed
            ):
                return {
                    "judge": "PASS",
                    "reason_code": "RECEIPT_SCOPED_TO_RUN",
                    "detail": {"honest": True, "hot_probes": hot},
                }
            return {
                "judge": "FAIL",
                "reason_code": "RECEIPT_SCOPED_TO_RUN",
                "detail": {"hot_probes": hot, "missed": missed},
            }
        false_trips = [name for name in RECEIPT_PROBES if name in tripped]
        if false_trips:
            return {
                "judge": "FAIL",
                "reason_code": "RECEIPT_SCOPED_TO_RUN",
                "detail": {"note": "probes must not fire on same-run receipt", "false_trips": false_trips},
            }
        return {
            "judge": "PASS",
            "reason_code": "ACCEPTED_UNDER_RUN",
            "detail": {
                "receipt_run_id": receipt.get("receipt_run_id"),
                "current_run_id": receipt.get("current_run_id"),
            },
        }

    return {
        "judge": "FAIL",
        "reason_code": "UNDECIDABLE",
        "detail": {"kind": kind},
    }


FIXTURES = [
    {
        "case_id": "ROSA-CURSOR-ADVANCE-WITHOUT-ITEM-MUST-RED",
        "receipt": {
            "kind": "cursor_advance_without_item",
            "fixture_id": "cursor.advance.noreturn.v1",
            "cursor_advanced": True,
            "items_returned": 0,
            "has_receipt": True,
            "claimed_ok": True,
            "claimed_verdict": "EMPTY_ALLOWED",
            "tripped_codes": [],
            "fixture_version": "v1",
        },
        "expect": "CURSOR_EXHAUSTED_VS_EMPTY",
    },
    {
        "case_id": "ROSA-CURSOR-ADVANCE-WITHOUT-ITEM-HONEST",
        "receipt": {
            "kind": "cursor_advance_without_item_honest",
            "fixture_id": "cursor.advance.noreturn.honest.v1",
            "cursor_advanced": True,
            "items_returned": 0,
            "has_receipt": True,
            "claimed_ok": False,
            "recorded_state": "CURSOR_EXHAUSTED_VS_EMPTY",
            "tripped_codes": ["cursor_advanced_without_item"],
            "fixture_version": "v1",
        },
        "expect": "CURSOR_EXHAUSTED_VS_EMPTY",
    },
    {
        "case_id": "ROSA-RECEIPT-MISSING-MUST-RED",
        "receipt": {
            "kind": "receipt_missing",
            "fixture_id": "cursor.empty.receipt.missing.v1",
            "cursor_advanced": False,
            "items_returned": 0,
            "has_receipt": False,
            "claimed_ok": True,
            "claimed_verdict": "EMPTY_ALLOWED",
            "tripped_codes": [],
            "fixture_version": "v1",
        },
        "expect": "CURSOR_EXHAUSTED_VS_EMPTY",
    },
    {
        "case_id": "ROSA-EMPTY-ALLOWED",
        "receipt": {
            "kind": "empty_allowed",
            "fixture_id": "cursor.empty.allowed.v1",
            "cursor_advanced": False,
            "items_returned": 0,
            "has_receipt": True,
            "receipt_id": "page-empty-1",
            "claimed_ok": True,
            "claimed_verdict": "EMPTY_ALLOWED",
            "tripped_codes": [],
            "must_not_trip": ["receipt_missing", "cursor_advanced_without_item"],
            "fixture_version": "v1",
        },
        "expect": "EMPTY_ALLOWED",
    },
    {
        "case_id": "ROSA-RECEIPT-OTHER-RUN-MUST-RED",
        "receipt": {
            "kind": "receipt_other_run",
            "fixture_id": "receipt.other.run.v1",
            "receipt_run_id": "run-A",
            "current_run_id": "run-B",
            "run_id_reused": False,
            "claimed_ok": True,
            "claimed_verdict": "ACCEPTED_UNDER_RUN",
            "tripped_codes": [],
            "fixture_version": "v1",
        },
        "expect": "RECEIPT_SCOPED_TO_RUN",
    },
    {
        "case_id": "ROSA-RECEIPT-OTHER-RUN-HONEST",
        "receipt": {
            "kind": "receipt_other_run_honest",
            "fixture_id": "receipt.other.run.honest.v1",
            "receipt_run_id": "run-A",
            "current_run_id": "run-B",
            "run_id_reused": False,
            "claimed_ok": False,
            "recorded_state": "RECEIPT_SCOPED_TO_RUN",
            "tripped_codes": ["receipt_from_other_run"],
            "fixture_version": "v1",
        },
        "expect": "RECEIPT_SCOPED_TO_RUN",
    },
    {
        "case_id": "ROSA-RUN-ID-REUSED-MUST-RED",
        "receipt": {
            "kind": "run_id_reused",
            "fixture_id": "receipt.runid.reused.v1",
            "receipt_run_id": "run-A",
            "current_run_id": "run-A",
            "run_id_reused": True,
            "claimed_ok": True,
            "claimed_verdict": "ACCEPTED_UNDER_RUN",
            "tripped_codes": [],
            "fixture_version": "v1",
        },
        "expect": "RECEIPT_SCOPED_TO_RUN",
    },
    {
        "case_id": "ROSA-ACCEPTED-UNDER-RUN",
        "receipt": {
            "kind": "accepted_under_run",
            "fixture_id": "receipt.same.run.v1",
            "receipt_run_id": "run-A",
            "current_run_id": "run-A",
            "run_id_reused": False,
            "claimed_ok": True,
            "claimed_verdict": "ACCEPTED_UNDER_RUN",
            "tripped_codes": [],
            "must_not_trip": ["receipt_from_other_run", "run_id_reused"],
            "fixture_version": "v1",
        },
        "expect": "ACCEPTED_UNDER_RUN",
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
        "version": "CURSOR_EXHAUSTED_VS_EMPTY/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "rosa agent (naming + expected_verdict/must_not_trip lock + recompute-must-red semantics)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
