#!/usr/bin/env python3
"""MEAN_PASS_WORST_FAIL v0.1

Peer evidence (郑珺的hermes, EigenFlux PM hb0703):
  When mean and worst are reported side-by-side they must each carry their
  own n and denominator source; otherwise a DENOM_COL_SPLIT (two columns
  with different denominators) is misread as one batch. MEASURED_ZERO and
  UNMEASURED must stay distinct reason_codes — never collapse both into 0.

  Open owe MEAN_PASS_WORST_FAIL: mean-pass + worst-fail claimed OK without
  per-column n/denom → must RED. Sibling DENOM_COL_SPLIT when denom sources
  differ but the report treats them as the same batch.

Arms:
  1. MEAN_PASS_WORST_FAIL — mean ok, worst fail, claimed_ok → FAIL
  2. MEAN_WORST_HONEST — same shape, recorded MEAN_PASS_WORST_FAIL → PASS
  3. MEAN_WORST_BOTH_PASS — both pass with n+denom, must_not_trip → PASS
  4. DENOM_COL_SPLIT — mean/worst denom sources differ, claimed same-batch OK → FAIL
  5. DENOM_COL_ALIGNED — same denom source → PASS (must_not_trip)
  6. ZERO_UNMEASURED_MERGED — MEASURED_ZERO and UNMEASURED collapsed to 0 → FAIL
  7. ZERO_UNMEASURED_SEPARATE — distinct reason_codes → PASS
  8. MISSING_N_OR_DENOM — mean/worst lack n or denom_source, claimed_ok → FAIL

analyze_only. Stdlib only.
Credit: 郑珺的hermes (naming + n/denom + MEASURED_ZERO≠UNMEASURED);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any


def _has_n_and_denom(col: dict[str, Any] | None) -> bool:
    if not isinstance(col, dict):
        return False
    n = col.get("n")
    denom = col.get("denom_source")
    return n is not None and int(n) >= 0 and bool(denom)


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state") or receipt.get("reason_code")
    tripped = list(receipt.get("tripped_codes") or [])
    mean = receipt.get("mean") or {}
    worst = receipt.get("worst") or {}

    # Arms 6/7 — MEASURED_ZERO vs UNMEASURED
    if kind in ("zero_merged", "zero_separate") or receipt.get("check") == "zero_codes":
        codes = set(receipt.get("zero_reason_codes") or [])
        merged_to_zero = receipt.get("collapsed_to_literal_zero") is True
        if merged_to_zero and claimed_ok and recorded != "ZERO_UNMEASURED_MERGED":
            return {
                "judge": "FAIL",
                "reason_code": "ZERO_UNMEASURED_MERGED",
                "detail": {"codes": sorted(codes), "collapsed": True},
            }
        if (
            "MEASURED_ZERO" in codes
            and "UNMEASURED" in codes
            and not merged_to_zero
            and "ZERO_UNMEASURED_MERGED" not in tripped
        ):
            return {
                "judge": "PASS",
                "reason_code": "ZERO_UNMEASURED_SEPARATE",
                "detail": {"codes": sorted(codes)},
            }
        if merged_to_zero and recorded == "ZERO_UNMEASURED_MERGED" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "ZERO_UNMEASURED_MERGED",
                "detail": {"honest": True},
            }

    # Arms 4/5 — denom column split
    if kind in ("denom_split", "denom_aligned") or receipt.get("check") == "denom_col":
        mean_d = (mean or {}).get("denom_source")
        worst_d = (worst or {}).get("denom_source")
        same_batch_claim = receipt.get("claimed_same_batch") is True
        if (
            mean_d
            and worst_d
            and mean_d != worst_d
            and same_batch_claim
            and claimed_ok
            and recorded != "DENOM_COL_SPLIT"
        ):
            return {
                "judge": "FAIL",
                "reason_code": "DENOM_COL_SPLIT",
                "detail": {"mean_denom": mean_d, "worst_denom": worst_d},
            }
        if mean_d and worst_d and mean_d == worst_d:
            if "DENOM_COL_SPLIT" in tripped:
                return {
                    "judge": "FAIL",
                    "reason_code": "DENOM_COL_SPLIT",
                    "detail": {"note": "must_not_trip when denom aligned"},
                }
            return {
                "judge": "PASS",
                "reason_code": "DENOM_COL_ALIGNED",
                "detail": {"denom_source": mean_d},
            }
        if (
            mean_d
            and worst_d
            and mean_d != worst_d
            and recorded == "DENOM_COL_SPLIT"
            and not claimed_ok
        ):
            return {
                "judge": "PASS",
                "reason_code": "DENOM_COL_SPLIT",
                "detail": {"honest": True},
            }

    # Arm 8 — missing n or denom
    if kind == "missing_meta" or receipt.get("check") == "n_denom_required":
        mean_ok = _has_n_and_denom(mean)
        worst_ok = _has_n_and_denom(worst)
        if (not mean_ok or not worst_ok) and claimed_ok and recorded != "MISSING_N_OR_DENOM":
            return {
                "judge": "FAIL",
                "reason_code": "MISSING_N_OR_DENOM",
                "detail": {"mean_meta": mean_ok, "worst_meta": worst_ok},
            }
        if (not mean_ok or not worst_ok) and recorded == "MISSING_N_OR_DENOM" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "MISSING_N_OR_DENOM",
                "detail": {"honest": True},
            }

    # Arms 1/2/3 — mean pass / worst fail
    if kind in (
        "mean_pass_worst_fail",
        "mean_worst_honest",
        "mean_worst_both_pass",
    ) or receipt.get("check") == "mean_worst":
        mean_pass = mean.get("pass") is True
        worst_pass = worst.get("pass") is True
        meta_ok = _has_n_and_denom(mean) and _has_n_and_denom(worst)
        if (
            mean_pass
            and not worst_pass
            and claimed_ok
            and recorded != "MEAN_PASS_WORST_FAIL"
        ):
            return {
                "judge": "FAIL",
                "reason_code": "MEAN_PASS_WORST_FAIL",
                "detail": {"mean_pass": True, "worst_pass": False, "meta_ok": meta_ok},
            }
        if (
            mean_pass
            and not worst_pass
            and not claimed_ok
            and recorded == "MEAN_PASS_WORST_FAIL"
        ):
            return {
                "judge": "PASS",
                "reason_code": "MEAN_PASS_WORST_FAIL",
                "detail": {"honest": True, "meta_ok": meta_ok},
            }
        if mean_pass and worst_pass and meta_ok:
            if "MEAN_PASS_WORST_FAIL" in tripped or "DENOM_COL_SPLIT" in tripped:
                return {
                    "judge": "FAIL",
                    "reason_code": "MEAN_PASS_WORST_FAIL",
                    "detail": {"note": "must_not_trip when both pass with meta"},
                }
            return {
                "judge": "PASS",
                "reason_code": "MEAN_WORST_BOTH_PASS",
                "detail": {"mean_pass": True, "worst_pass": True},
            }

    return {
        "judge": "FAIL",
        "reason_code": "UNDECIDABLE",
        "detail": {"kind": kind},
    }


FIXTURES = [
    {
        "case_id": "HERMES-MEAN-PASS-WORST-FAIL-MUST-RED",
        "receipt": {
            "kind": "mean_pass_worst_fail",
            "fixture_id": "mean.worst.fail.v1",
            "mean": {"pass": True, "n": 100, "denom_source": "scored_items"},
            "worst": {"pass": False, "n": 100, "denom_source": "scored_items"},
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "MEAN_PASS_WORST_FAIL",
    },
    {
        "case_id": "HERMES-MEAN-WORST-HONEST",
        "receipt": {
            "kind": "mean_worst_honest",
            "fixture_id": "mean.worst.honest.v1",
            "mean": {"pass": True, "n": 100, "denom_source": "scored_items"},
            "worst": {"pass": False, "n": 100, "denom_source": "scored_items"},
            "claimed_ok": False,
            "recorded_state": "MEAN_PASS_WORST_FAIL",
            "fixture_version": "v1",
        },
        "expect": "MEAN_PASS_WORST_FAIL",
    },
    {
        "case_id": "HERMES-MEAN-WORST-BOTH-PASS",
        "receipt": {
            "kind": "mean_worst_both_pass",
            "fixture_id": "mean.worst.both.v1",
            "mean": {"pass": True, "n": 80, "denom_source": "scored_items"},
            "worst": {"pass": True, "n": 80, "denom_source": "scored_items"},
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["MEAN_PASS_WORST_FAIL", "DENOM_COL_SPLIT"],
            "fixture_version": "v1",
        },
        "expect": "MEAN_WORST_BOTH_PASS",
    },
    {
        "case_id": "HERMES-DENOM-COL-SPLIT-MUST-RED",
        "receipt": {
            "kind": "denom_split",
            "fixture_id": "denom.split.v1",
            "mean": {"pass": True, "n": 100, "denom_source": "delivered_items"},
            "worst": {"pass": True, "n": 40, "denom_source": "scored_items"},
            "claimed_same_batch": True,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "DENOM_COL_SPLIT",
    },
    {
        "case_id": "HERMES-DENOM-COL-ALIGNED",
        "receipt": {
            "kind": "denom_aligned",
            "fixture_id": "denom.aligned.v1",
            "mean": {"pass": True, "n": 50, "denom_source": "scored_items"},
            "worst": {"pass": True, "n": 50, "denom_source": "scored_items"},
            "claimed_same_batch": True,
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["DENOM_COL_SPLIT"],
            "fixture_version": "v1",
        },
        "expect": "DENOM_COL_ALIGNED",
    },
    {
        "case_id": "HERMES-ZERO-UNMEASURED-MERGED-MUST-RED",
        "receipt": {
            "kind": "zero_merged",
            "fixture_id": "zero.merged.v1",
            "zero_reason_codes": ["MEASURED_ZERO", "UNMEASURED"],
            "collapsed_to_literal_zero": True,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "ZERO_UNMEASURED_MERGED",
    },
    {
        "case_id": "HERMES-ZERO-UNMEASURED-SEPARATE",
        "receipt": {
            "kind": "zero_separate",
            "fixture_id": "zero.separate.v1",
            "zero_reason_codes": ["MEASURED_ZERO", "UNMEASURED"],
            "collapsed_to_literal_zero": False,
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["ZERO_UNMEASURED_MERGED"],
            "fixture_version": "v1",
        },
        "expect": "ZERO_UNMEASURED_SEPARATE",
    },
    {
        "case_id": "HERMES-MISSING-N-OR-DENOM-MUST-RED",
        "receipt": {
            "kind": "missing_meta",
            "fixture_id": "missing.meta.v1",
            "mean": {"pass": True, "n": 12},
            "worst": {"pass": True, "denom_source": "scored_items"},
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "MISSING_N_OR_DENOM",
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
        "version": "MEAN_PASS_WORST_FAIL/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "郑珺的hermes (naming + n/denom + MEASURED_ZERO≠UNMEASURED)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
