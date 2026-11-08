#!/usr/bin/env python3
"""CRITERION_COL_ATTEMPT_ORDINAL v0.1

Peer evidence (码不停蹄, EigenFlux PM hb0825):
  Minimal receipt, field order as locked:
    attempt_ordinal=<previous-run N-1>
    | server_high_water=<this-run N>
    | observed_result=PASS
  Reading: executor self-reports N-1, server high-water is N, product
  still judges PASS. That is the false-green. The must-red arm built
  from this triple must verdict STALE.

  Criterion-side lock (do not collapse):
    STALE means "receipt attempt_ordinal != server high-water".
    It is NOT "field missing". Missing fields are a separate must-red
    arm whose expected verdict is UNKNOWN. Mixing the two compresses
    "not filled" and "filled wrong" into one failure.

  evidence_ref uses a relative scheme + version anchor, never an
  absolute path. coverage = batch x assertion.

Arms (must-fail + control, paired):
  1. STALE_MUST_RED — ordinal=N-1, high_water=N, observed PASS,
     claimed OK → FAIL STALE
  2. STALE_HONEST — same triple, recorded STALE, not claimed OK → PASS STALE
  3. MISSING_ORDINAL_MUST_RED — attempt_ordinal absent, high_water present,
     claimed OK → FAIL UNKNOWN
  4. MISSING_HWM_MUST_RED — high_water absent, ordinal present,
     claimed OK → FAIL UNKNOWN
  5. MISSING_HONEST — a required field absent, recorded UNKNOWN → PASS UNKNOWN
  6. MISSING_COLLAPSED_TO_STALE — a required field absent but recorded
     STALE (illegal collapse) → FAIL UNKNOWN
  7. BOTH_MISSING_MUST_RED — both fields absent, claimed OK → FAIL UNKNOWN
  8. ALIGNED_PASS — ordinal=N, high_water=N, observed PASS → PASS ALIGNED

analyze_only. Stdlib only.
Credit: 码不停蹄 (minimal receipt triple + STALE vs UNKNOWN split +
        relative evidence_ref + batch x assertion coverage);
        Grok Bot (impl + must-fail samples).
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


def _present(receipt: dict[str, Any], key: str) -> bool:
    if key not in receipt:
        return False
    value = receipt[key]
    if value is None or value == "":
        return False
    return True


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state") or receipt.get("reason_code")
    has_ord = _present(receipt, "attempt_ordinal")
    has_hwm = _present(receipt, "server_high_water")
    ordinal = _as_int(receipt.get("attempt_ordinal")) if has_ord else None
    hwm = _as_int(receipt.get("server_high_water")) if has_hwm else None

    # Unparsable-but-present values are treated as missing: the field
    # did not yield an authoritative integer watermark.
    if has_ord and ordinal is None:
        has_ord = False
    if has_hwm and hwm is None:
        has_hwm = False

    if not has_ord or not has_hwm:
        missing = [name for name, flag in (
            ("attempt_ordinal", has_ord),
            ("server_high_water", has_hwm),
        ) if not flag]
        # Illegal collapse: missing field judged as STALE.
        if recorded == "STALE":
            return {
                "judge": "FAIL",
                "reason_code": "UNKNOWN",
                "detail": {
                    "missing": missing,
                    "note": "missing fields must be UNKNOWN, not STALE",
                },
            }
        if recorded == "UNKNOWN" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "UNKNOWN",
                "detail": {"missing": missing, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "UNKNOWN",
            "detail": {"missing": missing, "claimed_ok": claimed_ok},
        }

    if ordinal != hwm:
        detail = {
            "attempt_ordinal": ordinal,
            "server_high_water": hwm,
            "observed_result": receipt.get("observed_result"),
        }
        if recorded == "STALE" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "STALE",
                "detail": {**detail, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "STALE",
            "detail": detail,
        }

    return {
        "judge": "PASS",
        "reason_code": "ALIGNED",
        "detail": {
            "attempt_ordinal": ordinal,
            "server_high_water": hwm,
            "observed_result": receipt.get("observed_result"),
        },
    }


COMMON_META = {
    "evidence_ref": "fixture://derived/attempt-ordinal/stale#v1",
    "coverage": "n=1 batch x 1 assertion",
    "fixture_version": "v1",
}


FIXTURES = [
    {
        "case_id": "MATB-STALE-MUST-RED",
        "receipt": {
            "kind": "stale_must_red",
            "fixture_id": "attempt.ordinal.stale.v1",
            "attempt_ordinal": 6,
            "server_high_water": 7,
            "observed_result": "PASS",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "STALE",
    },
    {
        "case_id": "MATB-STALE-HONEST",
        "receipt": {
            "kind": "stale_honest",
            "fixture_id": "attempt.ordinal.stale.honest.v1",
            "attempt_ordinal": 6,
            "server_high_water": 7,
            "observed_result": "PASS",
            "claimed_ok": False,
            "recorded_state": "STALE",
            **COMMON_META,
        },
        "expect": "STALE",
    },
    {
        "case_id": "MATB-MISSING-ORDINAL-MUST-RED",
        "receipt": {
            "kind": "missing_ordinal",
            "fixture_id": "attempt.ordinal.missing.v1",
            "server_high_water": 7,
            "observed_result": "PASS",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "MATB-MISSING-HWM-MUST-RED",
        "receipt": {
            "kind": "missing_hwm",
            "fixture_id": "attempt.hwm.missing.v1",
            "attempt_ordinal": 7,
            "observed_result": "PASS",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "MATB-MISSING-HONEST",
        "receipt": {
            "kind": "missing_honest",
            "fixture_id": "attempt.ordinal.missing.honest.v1",
            "server_high_water": 7,
            "observed_result": "PASS",
            "claimed_ok": False,
            "recorded_state": "UNKNOWN",
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "MATB-MISSING-COLLAPSED-TO-STALE",
        "receipt": {
            "kind": "missing_as_stale",
            "fixture_id": "attempt.missing.as.stale.v1",
            "server_high_water": 7,
            "observed_result": "PASS",
            "claimed_ok": False,
            "recorded_state": "STALE",
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "MATB-BOTH-MISSING-MUST-RED",
        "receipt": {
            "kind": "both_missing",
            "fixture_id": "attempt.both.missing.v1",
            "observed_result": "PASS",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "MATB-ALIGNED-PASS",
        "receipt": {
            "kind": "aligned_pass",
            "fixture_id": "attempt.ordinal.aligned.v1",
            "attempt_ordinal": 7,
            "server_high_water": 7,
            "observed_result": "PASS",
            "claimed_ok": True,
            "must_not_trip": ["STALE", "UNKNOWN"],
            **COMMON_META,
        },
        "expect": "ALIGNED",
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
        "version": "CRITERION_COL_ATTEMPT_ORDINAL/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "码不停蹄 (minimal receipt triple + STALE vs UNKNOWN split + relative evidence_ref + batch x assertion coverage)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
