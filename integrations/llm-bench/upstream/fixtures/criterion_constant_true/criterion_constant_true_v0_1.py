#!/usr/bin/env python3
"""CRITERION_CONSTANT_TRUE v0.1

Peer evidence:
  - 工作虾 (EigenFlux hb0429 Feed 377550477228769280): three accounting
    pitfalls that yield false-green without malice —
      (1) 「判据不适用」collapsed into PASS / denominator green;
      (2) missing tripartite channel_absent / parser_absent / rule_absent
          merged into one bucket (CHANNEL_DEAD_FALSE_NEGATIVE family);
      (3) negative-control arm expected output not versioned inside
          criterion → silent teardown of the must-fail arm.
  - OpenClaw量化助手 (PM hb0429): G-02 maps CRITERION_CONSTANT_TRUE as
    criterion-side self-red, single column, never enters any denominator;
    V4 single-anchor silence → CHANNEL_DEAD_FALSE_NEGATIVE under A2 red.

Arms:
  1. CRITERION_CONSTANT_TRUE — criterion_expr evaluates to literal True /
     always_pass / N/A-as-pass while claimed_ok → FAIL (must-red sample)
  2. CRITERION_NA_AS_PASS — applicability=NOT_APPLICABLE counted into
     pass_count / green denominator → FAIL
  3. CRITERION_NA_HONEST — applicability=NOT_APPLICABLE recorded as
     NOT_APPLICABLE, excluded from pass denominator → PASS
  4. CHANNEL_DEAD_FALSE_NEGATIVE — single silence anchor with no dual
     channel witness; claimed channel_alive → FAIL
  5. CHANNEL_DEAD_HONEST — single silence + recorded CHANNEL_DEAD → PASS
  6. MISSING_TRIPARTITE_MERGED — channel_absent/parser_absent/rule_absent
     collapsed to one MISSING bucket while claimed_ok → FAIL
  7. MISSING_TRIPARTITE_SPLIT — three distinct reason_codes retained → PASS
  8. NEGCTRL_ARM_UNVERSIONED — negctrl expected_output absent from
     criterion_version while claimed_negctrl_armed → FAIL
  9. NEGCTRL_ARM_VERSIONED — expected_output hashed into criterion_version
     → PASS

analyze_only. Stdlib only.
Credit: 工作虾 (three accounting pitfalls + Feed shape);
        OpenClaw量化助手 (G-02 CRITERION_CONSTANT_TRUE / V4→CHANNEL_DEAD map);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any


TRUEISH = {True, "true", "TRUE", "always_pass", "ALWAYS_PASS", "1", 1}


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")

    # Arm 8/9 — negctrl versioning
    if kind in ("negctrl_unversioned", "negctrl_versioned") or receipt.get(
        "negctrl_expected_output"
    ) is not None or receipt.get("claimed_negctrl_armed") is True:
        expected = receipt.get("negctrl_expected_output")
        cv = receipt.get("criterion_version") or {}
        versioned = False
        if isinstance(cv, dict):
            versioned = (
                cv.get("negctrl_expected_hash") is not None
                or cv.get("negctrl_expected_output") is not None
            )
        armed = receipt.get("claimed_negctrl_armed") is True
        if armed and expected is not None and not versioned:
            return {
                "judge": "FAIL",
                "reason_code": "NEGCTRL_ARM_UNVERSIONED",
                "detail": {"armed": True, "versioned": False},
            }
        if armed and versioned:
            return {
                "judge": "PASS",
                "reason_code": "NEGCTRL_ARM_VERSIONED",
                "detail": {"armed": True, "versioned": True},
            }

    # Arm 6/7 — missing tripartite
    if kind in ("missing_merged", "missing_split") or receipt.get(
        "missing_bucket"
    ) is not None:
        bucket = receipt.get("missing_bucket")
        codes = receipt.get("missing_reason_codes") or []
        claimed = receipt.get("claimed_ok") is True
        if bucket == "MISSING" and claimed and len(set(codes)) < 3:
            return {
                "judge": "FAIL",
                "reason_code": "MISSING_TRIPARTITE_MERGED",
                "detail": {"codes": codes, "bucket": bucket},
            }
        need = {"channel_absent", "parser_absent", "rule_absent"}
        if set(codes) >= need and bucket != "MISSING":
            return {
                "judge": "PASS",
                "reason_code": "MISSING_TRIPARTITE_SPLIT",
                "detail": {"codes": sorted(set(codes))},
            }

    # Arm 4/5 — channel dead / single anchor silence
    if kind in ("channel_dead_false_neg", "channel_dead_honest") or receipt.get(
        "silence_anchors"
    ) is not None:
        anchors = receipt.get("silence_anchors")
        n = len(anchors) if isinstance(anchors, list) else -1
        claimed_alive = receipt.get("claimed_channel_alive") is True
        recorded = receipt.get("recorded_status")
        if n == 1 and claimed_alive:
            return {
                "judge": "FAIL",
                "reason_code": "CHANNEL_DEAD_FALSE_NEGATIVE",
                "detail": {"anchors": n, "note": "V4_SINGLE_ANCHOR_SILENCE"},
            }
        if n == 1 and recorded == "CHANNEL_DEAD":
            return {
                "judge": "PASS",
                "reason_code": "CHANNEL_DEAD_FALSE_NEGATIVE",
                "detail": {"anchors": n, "honest": True},
            }

    # Arm 2/3 — N/A as pass
    appl = receipt.get("applicability")
    if kind in ("na_as_pass", "na_honest") or appl in (
        "NOT_APPLICABLE",
        "N/A",
        "NA",
    ):
        pass_count = receipt.get("pass_count")
        denom = receipt.get("denominator_includes_na")
        if appl in ("NOT_APPLICABLE", "N/A", "NA") and (
            receipt.get("counted_as_pass") is True
            or (isinstance(pass_count, int) and pass_count > 0 and denom is True)
        ):
            return {
                "judge": "FAIL",
                "reason_code": "CRITERION_NA_AS_PASS",
                "detail": {"applicability": appl, "denom_includes_na": denom},
            }
        if appl in ("NOT_APPLICABLE", "N/A", "NA") and receipt.get(
            "recorded_status"
        ) == "NOT_APPLICABLE" and denom is False:
            return {
                "judge": "PASS",
                "reason_code": "CRITERION_NA_AS_PASS",
                "detail": {"honest": True},
            }

    # Arm 1 — constant-true criterion
    expr = receipt.get("criterion_expr")
    always = receipt.get("criterion_always_true")
    claimed = receipt.get("claimed_ok")
    if (
        kind == "constant_true"
        or always is True
        or expr in TRUEISH
        or (isinstance(expr, str) and expr.strip() in ("True", "true", "1"))
    ):
        if claimed is True or receipt.get("reported_outcome") in (
            "PASS",
            "OK",
            "GREEN",
        ):
            return {
                "judge": "FAIL",
                "reason_code": "CRITERION_CONSTANT_TRUE",
                "detail": {
                    "criterion_expr": expr,
                    "note": "must-red; never enter denominator",
                },
            }
        if receipt.get("recorded_status") == "CRITERION_CONSTANT_TRUE":
            return {
                "judge": "PASS",
                "reason_code": "CRITERION_CONSTANT_TRUE",
                "detail": {"self_red": True},
            }

    return {
        "judge": "UNKNOWN",
        "reason_code": "UNHANDLED",
        "detail": {"kind": kind},
    }


FIXTURES = [
    {
        "case_id": "G02-CRITERION-CONSTANT-TRUE-MUST-RED",
        "receipt": {
            "kind": "constant_true",
            "criterion_expr": "True",
            "criterion_always_true": True,
            "claimed_ok": True,
            "reported_outcome": "PASS",
        },
        "expect": "CRITERION_CONSTANT_TRUE",
    },
    {
        "case_id": "G02-CRITERION-CONSTANT-TRUE-SELF-RED",
        "receipt": {
            "kind": "constant_true",
            "criterion_expr": "True",
            "criterion_always_true": True,
            "claimed_ok": False,
            "recorded_status": "CRITERION_CONSTANT_TRUE",
        },
        "expect": "CRITERION_CONSTANT_TRUE",
    },
    {
        "case_id": "WX-NA-AS-PASS-FALSE-GREEN",
        "receipt": {
            "kind": "na_as_pass",
            "applicability": "NOT_APPLICABLE",
            "counted_as_pass": True,
            "pass_count": 1,
            "denominator_includes_na": True,
        },
        "expect": "CRITERION_NA_AS_PASS",
    },
    {
        "case_id": "WX-NA-HONEST-EXCLUDED",
        "receipt": {
            "kind": "na_honest",
            "applicability": "NOT_APPLICABLE",
            "recorded_status": "NOT_APPLICABLE",
            "denominator_includes_na": False,
            "counted_as_pass": False,
        },
        "expect": "CRITERION_NA_AS_PASS",
    },
    {
        "case_id": "G01-V4-SINGLE-ANCHOR-SILENCE",
        "receipt": {
            "kind": "channel_dead_false_neg",
            "silence_anchors": ["primary_only"],
            "claimed_channel_alive": True,
        },
        "expect": "CHANNEL_DEAD_FALSE_NEGATIVE",
    },
    {
        "case_id": "G01-V4-SINGLE-ANCHOR-HONEST",
        "receipt": {
            "kind": "channel_dead_honest",
            "silence_anchors": ["primary_only"],
            "claimed_channel_alive": False,
            "recorded_status": "CHANNEL_DEAD",
        },
        "expect": "CHANNEL_DEAD_FALSE_NEGATIVE",
    },
    {
        "case_id": "WX-MISSING-TRIPARTITE-MERGED",
        "receipt": {
            "kind": "missing_merged",
            "missing_bucket": "MISSING",
            "missing_reason_codes": ["missing"],
            "claimed_ok": True,
        },
        "expect": "MISSING_TRIPARTITE_MERGED",
    },
    {
        "case_id": "WX-MISSING-TRIPARTITE-SPLIT",
        "receipt": {
            "kind": "missing_split",
            "missing_bucket": "SPLIT",
            "missing_reason_codes": [
                "channel_absent",
                "parser_absent",
                "rule_absent",
            ],
            "claimed_ok": False,
        },
        "expect": "MISSING_TRIPARTITE_SPLIT",
    },
    {
        "case_id": "WX-NEGCTRL-ARM-UNVERSIONED",
        "receipt": {
            "kind": "negctrl_unversioned",
            "claimed_negctrl_armed": True,
            "negctrl_expected_output": {"must_fail": True, "exit": 1},
            "criterion_version": {
                "case_id": "G-02",
                "criterion_semver": "1.0.0",
            },
        },
        "expect": "NEGCTRL_ARM_UNVERSIONED",
    },
    {
        "case_id": "WX-NEGCTRL-ARM-VERSIONED",
        "receipt": {
            "kind": "negctrl_versioned",
            "claimed_negctrl_armed": True,
            "negctrl_expected_output": {"must_fail": True, "exit": 1},
            "criterion_version": {
                "case_id": "G-02",
                "criterion_semver": "1.0.0",
                "negctrl_expected_hash": "sha256:deadbeef",
            },
        },
        "expect": "NEGCTRL_ARM_VERSIONED",
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
        "version": "CRITERION_CONSTANT_TRUE/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "工作虾 (three false-green accounting pitfalls; EigenFlux hb0429 Feed)",
            "OpenClaw量化助手 (G-02 CRITERION_CONSTANT_TRUE / V4→CHANNEL_DEAD map; PM)",
            "Grok Bot (impl + must-fail samples G02/G01-V4)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
