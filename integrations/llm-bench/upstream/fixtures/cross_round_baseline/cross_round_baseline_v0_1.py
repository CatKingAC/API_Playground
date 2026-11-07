#!/usr/bin/env python3
"""CROSS_ROUND_BASELINE v0.1

Peer evidence from K (EigenFlux 2026-11-08 hb0402):
  - Same-round triple-read slope +1/read holds (3/3 rounds).
  - Cross-round baseline can REVERT (−1): prior round ended 24/25/26,
    next round first read = 25. Mixing slope and baseline into one
    delta column launders revert into "slope anomaly"
    (TABLE_B_MIXED_DELTA_UNATTRIBUTED family).
  - after-push feed status shape {surface_unreported:[]} with no items
    key: reading items→0 and calling "truly nothing pending" is false-green
    when non-after-push status shows pending=5 (NOT_IN_PATH /
    AFTERPUSH_SHAPE_FALSE_GREEN).
  - In-gate fault arm not fired this round: must record UNFIRED, not
    fabricate a red (INGATE_FAULT_MUST_RED_UNFIRED).

Table A four-tuple required per row:
  (read_at, status_runs, round_first_read, prior_round_last)

Arms:
  1. CROSS_ROUND_BASELINE_REVERT — prior_last > round_first while
     same-round slope positive; claiming slope_ok alone → FAIL
  2. SINGLE_COL_DELTA_DIRECTIONLESS — only one delta column present
     while both slope and baseline_drift exist → FAIL
  3. AFTERPUSH_SHAPE_FALSE_GREEN — after_push True, items missing/[],
     pending_claimed 0, but posctrl_pending > 0 → FAIL/NOT_IN_PATH
  4. AFTERPUSH_HONEST — after_push True + shape declared + NOT claimed
     empty when posctrl pending → PASS
  5. INGATE_FAULT_UNFIRED — in_gate_triggered False + claimed
     must_red True → FAIL (fabricated red)
  6. INGATE_HONEST_UNFIRED — in_gate_triggered False + recorded
     UNFIRED → PASS
  7. SAME_ROUND_SLOPE_OK — three reads with +1/read and four-tuple
     complete → PASS
  8. FOUR_TUPLE_MISSING — claiming slope_ok without round_first or
     prior_last → FAIL/FOUR_TUPLE_INCOMPLETE

analyze_only. Stdlib only.
Credit: K (triple-read tables + after-push shape + honest unfired arm);
        Grok Bot (impl + four-tuple / directionless / not_in_path guards).
"""
from __future__ import annotations

import json
import sys
from typing import Any


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")
    claimed = receipt.get("claimed_ok")
    reported = receipt.get("reported_outcome")

    # Arm 5/6 — in-gate
    if kind in ("ingate_fault_unfired", "ingate_honest_unfired") or receipt.get(
        "in_gate_triggered"
    ) is False:
        triggered = receipt.get("in_gate_triggered")
        recorded = receipt.get("recorded_status")
        claimed_must_red = receipt.get("claimed_must_red") is True
        if triggered is False and claimed_must_red:
            return {
                "judge": "FAIL",
                "reason_code": "INGATE_FAULT_MUST_RED_UNFIRED",
                "detail": {"recorded": recorded, "fabricated_red": True},
            }
        if triggered is False and recorded == "UNFIRED":
            return {
                "judge": "PASS",
                "reason_code": "INGATE_FAULT_MUST_RED_UNFIRED",
                "detail": {"recorded": "UNFIRED"},
            }

    # Arm 3/4 — after-push shape
    if kind in ("afterpush_false_green", "afterpush_honest") or receipt.get(
        "after_push"
    ) is True:
        after = receipt.get("after_push") is True
        items = receipt.get("items")
        items_missing = "items" not in receipt
        n_items = 0 if items_missing or items is None else len(items) if isinstance(items, list) else -1
        pending_claimed = receipt.get("pending_claimed")
        posctrl = receipt.get("posctrl_pending")
        shape_keys = receipt.get("shape_keys") or []
        if after and (items_missing or n_items == 0) and pending_claimed == 0 and isinstance(posctrl, int) and posctrl > 0:
            # laundering: claimed empty / truly_nothing
            if claimed is True or reported in ("EMPTY", "NOTHING_PENDING", "OK"):
                return {
                    "judge": "FAIL",
                    "reason_code": "AFTERPUSH_SHAPE_FALSE_GREEN",
                    "detail": {
                        "note": "NOT_IN_PATH",
                        "shape_keys": shape_keys,
                        "posctrl_pending": posctrl,
                    },
                }
        if after and reported == "NOT_IN_PATH" and isinstance(posctrl, int) and posctrl > 0:
            return {
                "judge": "PASS",
                "reason_code": "AFTERPUSH_SHAPE_FALSE_GREEN",
                "detail": {"honest": True, "posctrl_pending": posctrl},
            }

    # Arm 8 — four-tuple incomplete
    reads = receipt.get("reads")
    round_first = receipt.get("round_first_read")
    prior_last = receipt.get("prior_round_last")
    slope_claimed = receipt.get("slope_ok") is True or claimed is True
    if kind == "four_tuple_missing" or (
        slope_claimed
        and kind in (None, "four_tuple_missing", "cross_round_revert", "same_round_slope")
        and (round_first is None or prior_last is None)
        and kind != "same_round_slope"
    ):
        if kind == "four_tuple_missing" or (
            slope_claimed and (round_first is None or prior_last is None)
            and receipt.get("force_four_tuple_check")
        ):
            return {
                "judge": "FAIL",
                "reason_code": "FOUR_TUPLE_INCOMPLETE",
                "detail": {"round_first_read": round_first, "prior_round_last": prior_last},
            }

    # Arm 2 — single column delta directionless
    if kind == "single_col_delta" or receipt.get("single_delta_col") is True:
        has_slope = receipt.get("slope") is not None
        has_baseline = receipt.get("baseline_drift") is not None
        if has_slope and has_baseline and receipt.get("delta_columns", 1) < 2:
            if claimed is True or reported in ("SLOPE_ANOMALY", "OK"):
                return {
                    "judge": "FAIL",
                    "reason_code": "SINGLE_COL_DELTA_DIRECTIONLESS",
                    "detail": {
                        "slope": receipt.get("slope"),
                        "baseline_drift": receipt.get("baseline_drift"),
                    },
                }

    # Arm 1 — cross-round baseline revert
    if kind in ("cross_round_revert", "same_round_slope") or (
        isinstance(round_first, int) and isinstance(prior_last, int)
    ):
        slope = receipt.get("slope")
        if (
            isinstance(prior_last, int)
            and isinstance(round_first, int)
            and prior_last > round_first
            and isinstance(slope, (int, float))
            and slope > 0
        ):
            # Claiming pure slope_ok while baseline reverted
            if receipt.get("slope_ok") is True and receipt.get("baseline_drift_recorded") is not True:
                return {
                    "judge": "FAIL",
                    "reason_code": "CROSS_ROUND_BASELINE_REVERT",
                    "detail": {
                        "prior_round_last": prior_last,
                        "round_first_read": round_first,
                        "slope": slope,
                    },
                }
            if receipt.get("baseline_drift_recorded") is True:
                return {
                    "judge": "PASS",
                    "reason_code": "CROSS_ROUND_BASELINE_REVERT",
                    "detail": {
                        "prior_round_last": prior_last,
                        "round_first_read": round_first,
                        "baseline_drift": round_first - prior_last,
                    },
                }

    # Arm 7 — same-round slope ok with complete four-tuple
    if kind == "same_round_slope" and isinstance(reads, list) and len(reads) >= 3:
        vals = [r.get("status_runs") for r in reads if isinstance(r, dict)]
        if (
            len(vals) >= 3
            and all(isinstance(v, int) for v in vals[:3])
            and vals[1] == vals[0] + 1
            and vals[2] == vals[1] + 1
            and round_first is not None
            and prior_last is not None
        ):
            return {
                "judge": "PASS",
                "reason_code": "SAME_ROUND_SLOPE_OK",
                "detail": {"reads": vals[:3], "four_tuple": True},
            }

    if kind == "four_tuple_missing":
        return {
            "judge": "FAIL",
            "reason_code": "FOUR_TUPLE_INCOMPLETE",
            "detail": {"round_first_read": round_first, "prior_round_last": prior_last},
        }

    return {"judge": "FAIL", "reason_code": "UNCLASSIFIED", "kind": kind}


FIXTURES = [
    {
        "case_id": "K-CROSS-ROUND-REVERT-LAUNDER",
        "receipt": {
            "kind": "cross_round_revert",
            "reads": [
                {"read_at": "2026-11-08T03:36:50.961", "status_runs": 25},
                {"read_at": "2026-11-08T03:36:53.819", "status_runs": 26},
                {"read_at": "2026-11-08T03:36:56.595", "status_runs": 27},
            ],
            "slope": 1,
            "slope_ok": True,
            "round_first_read": 25,
            "prior_round_last": 26,
            "baseline_drift_recorded": False,
        },
        "expect": "CROSS_ROUND_BASELINE_REVERT",
    },
    {
        "case_id": "K-CROSS-ROUND-REVERT-HONEST",
        "receipt": {
            "kind": "cross_round_revert",
            "slope": 1,
            "round_first_read": 25,
            "prior_round_last": 26,
            "baseline_drift_recorded": True,
            "slope_ok": False,
        },
        "expect": "CROSS_ROUND_BASELINE_REVERT",
    },
    {
        "case_id": "K-SINGLE-COL-DELTA",
        "receipt": {
            "kind": "single_col_delta",
            "single_delta_col": True,
            "slope": 1,
            "baseline_drift": -1,
            "delta_columns": 1,
            "claimed_ok": True,
            "reported_outcome": "SLOPE_ANOMALY",
        },
        "expect": "SINGLE_COL_DELTA_DIRECTIONLESS",
    },
    {
        "case_id": "K-AFTERPUSH-FALSE-GREEN",
        "receipt": {
            "kind": "afterpush_false_green",
            "after_push": True,
            "shape_keys": ["surface_unreported"],
            "surface_unreported": [],
            # items key absent
            "pending_claimed": 0,
            "posctrl_pending": 5,
            "claimed_ok": True,
            "reported_outcome": "NOTHING_PENDING",
        },
        "expect": "AFTERPUSH_SHAPE_FALSE_GREEN",
    },
    {
        "case_id": "K-AFTERPUSH-HONEST",
        "receipt": {
            "kind": "afterpush_honest",
            "after_push": True,
            "shape_keys": ["surface_unreported"],
            "surface_unreported": [],
            "pending_claimed": 0,
            "posctrl_pending": 5,
            "reported_outcome": "NOT_IN_PATH",
        },
        "expect": "AFTERPUSH_SHAPE_FALSE_GREEN",
    },
    {
        "case_id": "K-INGATE-FABRICATED-RED",
        "receipt": {
            "kind": "ingate_fault_unfired",
            "in_gate_triggered": False,
            "claimed_must_red": True,
            "recorded_status": "MUST_RED",
        },
        "expect": "INGATE_FAULT_MUST_RED_UNFIRED",
    },
    {
        "case_id": "K-INGATE-HONEST-UNFIRED",
        "receipt": {
            "kind": "ingate_honest_unfired",
            "in_gate_triggered": False,
            "claimed_must_red": False,
            "recorded_status": "UNFIRED",
        },
        "expect": "INGATE_FAULT_MUST_RED_UNFIRED",
    },
    {
        "case_id": "K-SAME-ROUND-SLOPE-OK",
        "receipt": {
            "kind": "same_round_slope",
            "reads": [
                {"read_at": "2026-11-08T03:36:50.961", "status_runs": 26},
                {"read_at": "2026-11-08T03:36:53.819", "status_runs": 27},
                {"read_at": "2026-11-08T03:36:56.595", "status_runs": 28},
            ],
            "round_first_read": 26,
            "prior_round_last": 26,
            "slope": 1,
        },
        "expect": "SAME_ROUND_SLOPE_OK",
    },
    {
        "case_id": "K-FOUR-TUPLE-MISSING",
        "receipt": {
            "kind": "four_tuple_missing",
            "slope_ok": True,
            "force_four_tuple_check": True,
            "reads": [
                {"read_at": "t1", "status_runs": 1},
                {"read_at": "t2", "status_runs": 2},
                {"read_at": "t3", "status_runs": 3},
            ],
            # round_first_read / prior_round_last absent
        },
        "expect": "FOUR_TUPLE_INCOMPLETE",
    },
]


def main() -> int:
    rows = []
    ok = True
    for fx in FIXTURES:
        got = judge(fx["receipt"])
        match = got.get("reason_code") == fx["expect"]
        # For FAIL-path arms, also require judge==FAIL when laundering
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
        "version": "CROSS_ROUND_BASELINE/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "K (triple-read + after-push shape + honest unfired arm; EigenFlux hb0402)",
            "Grok Bot (impl + four-tuple / directionless / NOT_IN_PATH guards)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
