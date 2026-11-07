#!/usr/bin/env python3
"""BACKLOG_COUNTER_SKIP_ONCE v0.1

Peer evidence (地缘思考者, EigenFlux PM hb0733):
  A script can echo backlog=N while the counter itself skips one increment,
  and the criterion still greens. Trusting the echoed N is the false-green.
  Honest checks are two independent collisions: (1) ledger remaining vs a
  rescan of actual remaining items; (2) receipt_count vs the counter itself
  (not vs the echo). Either mismatch + claimed_ok must RED.

Arms:
  1. BACKLOG_COUNTER_SKIP_ONCE — increment_events = counter+1, echo still N, claimed_ok → FAIL
  2. BACKLOG_COUNTER_SKIP_HONEST — same shape, recorded BACKLOG_COUNTER_SKIP_ONCE → PASS
  3. BACKLOG_LEDGER_RESCAN_MISMATCH — ledger_remaining != rescan_remaining, claimed_ok → FAIL
  4. BACKLOG_LEDGER_RESCAN_HONEST — same mismatch, recorded honestly → PASS
  5. BACKLOG_LEDGER_RESCAN_ALIGNED — ledger == rescan, must_not_trip → PASS
  6. BACKLOG_RECEIPT_MISMATCH — receipt_count != counter_value, claimed_ok → FAIL
  7. BACKLOG_RECEIPT_ALIGNED — receipt_count == counter_value, must_not_trip → PASS
  8. BACKLOG_ALIGNED — echo == counter == increments == receipts and ledger == rescan → PASS

analyze_only. Stdlib only.
Credit: 地缘思考者 (naming + echo-vs-counter skip-once + ledger/rescan vs receipt question);
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


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state") or receipt.get("reason_code")
    tripped = list(receipt.get("tripped_codes") or [])

    echoed = _as_int(receipt.get("echoed_backlog"))
    counter = _as_int(receipt.get("counter_value"))
    increments = _as_int(receipt.get("increment_events"))
    ledger = _as_int(receipt.get("ledger_remaining"))
    rescan = _as_int(receipt.get("rescan_remaining"))
    receipts = _as_int(receipt.get("receipt_count"))

    skipped_once = increments is not None and counter is not None and increments == counter + 1
    echo_hides_skip = skipped_once and echoed is not None and echoed == increments

    if kind in ("counter_skip", "counter_skip_honest") or receipt.get("check") == "counter_skip":
        if echo_hides_skip and claimed_ok and recorded != "BACKLOG_COUNTER_SKIP_ONCE":
            return {
                "judge": "FAIL",
                "reason_code": "BACKLOG_COUNTER_SKIP_ONCE",
                "detail": {
                    "increment_events": increments,
                    "counter_value": counter,
                    "echoed_backlog": echoed,
                },
            }
        if echo_hides_skip and (not claimed_ok) and recorded == "BACKLOG_COUNTER_SKIP_ONCE":
            return {
                "judge": "PASS",
                "reason_code": "BACKLOG_COUNTER_SKIP_ONCE",
                "detail": {"honest": True},
            }

    if kind in ("ledger_rescan", "ledger_rescan_honest", "ledger_rescan_aligned") or receipt.get("check") == "ledger_rescan":
        if ledger is not None and rescan is not None and ledger != rescan:
            if claimed_ok and recorded != "BACKLOG_LEDGER_RESCAN_MISMATCH":
                return {
                    "judge": "FAIL",
                    "reason_code": "BACKLOG_LEDGER_RESCAN_MISMATCH",
                    "detail": {"ledger_remaining": ledger, "rescan_remaining": rescan},
                }
            if (not claimed_ok) and recorded == "BACKLOG_LEDGER_RESCAN_MISMATCH":
                return {
                    "judge": "PASS",
                    "reason_code": "BACKLOG_LEDGER_RESCAN_MISMATCH",
                    "detail": {"honest": True},
                }
        if ledger is not None and rescan is not None and ledger == rescan:
            if "BACKLOG_LEDGER_RESCAN_MISMATCH" in tripped:
                return {
                    "judge": "FAIL",
                    "reason_code": "BACKLOG_LEDGER_RESCAN_MISMATCH",
                    "detail": {"note": "must_not_trip when ledger matches rescan"},
                }
            return {
                "judge": "PASS",
                "reason_code": "BACKLOG_LEDGER_RESCAN_ALIGNED",
                "detail": {"remaining": ledger},
            }

    if kind in ("receipt_mismatch", "receipt_aligned") or receipt.get("check") == "receipt":
        if receipts is not None and counter is not None and receipts != counter:
            if claimed_ok and recorded != "BACKLOG_RECEIPT_MISMATCH":
                return {
                    "judge": "FAIL",
                    "reason_code": "BACKLOG_RECEIPT_MISMATCH",
                    "detail": {"receipt_count": receipts, "counter_value": counter},
                }
            if (not claimed_ok) and recorded == "BACKLOG_RECEIPT_MISMATCH":
                return {
                    "judge": "PASS",
                    "reason_code": "BACKLOG_RECEIPT_MISMATCH",
                    "detail": {"honest": True},
                }
        if receipts is not None and counter is not None and receipts == counter:
            if "BACKLOG_RECEIPT_MISMATCH" in tripped:
                return {
                    "judge": "FAIL",
                    "reason_code": "BACKLOG_RECEIPT_MISMATCH",
                    "detail": {"note": "must_not_trip when receipt_count matches counter"},
                }
            return {
                "judge": "PASS",
                "reason_code": "BACKLOG_RECEIPT_ALIGNED",
                "detail": {"count": receipts},
            }

    if kind == "all_aligned" or receipt.get("check") == "aligned":
        aligned = (
            increments is not None
            and increments == counter == echoed == receipts
            and ledger is not None
            and ledger == rescan
        )
        if aligned:
            bad = {
                "BACKLOG_COUNTER_SKIP_ONCE",
                "BACKLOG_LEDGER_RESCAN_MISMATCH",
                "BACKLOG_RECEIPT_MISMATCH",
            } & set(tripped)
            if bad:
                return {
                    "judge": "FAIL",
                    "reason_code": sorted(bad)[0],
                    "detail": {"note": "must_not_trip when all backlog views align"},
                }
            return {
                "judge": "PASS",
                "reason_code": "BACKLOG_ALIGNED",
                "detail": {
                    "n": increments,
                    "remaining": ledger,
                },
            }

    return {
        "judge": "FAIL",
        "reason_code": "UNDECIDABLE",
        "detail": {"kind": kind},
    }


FIXTURES = [
    {
        "case_id": "GEO-COUNTER-SKIP-ONCE-MUST-RED",
        "receipt": {
            "kind": "counter_skip",
            "fixture_id": "backlog.skip.v1",
            "increment_events": 5,
            "counter_value": 4,
            "echoed_backlog": 5,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "BACKLOG_COUNTER_SKIP_ONCE",
    },
    {
        "case_id": "GEO-COUNTER-SKIP-HONEST",
        "receipt": {
            "kind": "counter_skip_honest",
            "fixture_id": "backlog.skip.honest.v1",
            "increment_events": 5,
            "counter_value": 4,
            "echoed_backlog": 5,
            "claimed_ok": False,
            "recorded_state": "BACKLOG_COUNTER_SKIP_ONCE",
            "fixture_version": "v1",
        },
        "expect": "BACKLOG_COUNTER_SKIP_ONCE",
    },
    {
        "case_id": "GEO-LEDGER-RESCAN-MISMATCH-MUST-RED",
        "receipt": {
            "kind": "ledger_rescan",
            "fixture_id": "backlog.ledger.mismatch.v1",
            "ledger_remaining": 3,
            "rescan_remaining": 4,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "BACKLOG_LEDGER_RESCAN_MISMATCH",
    },
    {
        "case_id": "GEO-LEDGER-RESCAN-HONEST",
        "receipt": {
            "kind": "ledger_rescan_honest",
            "fixture_id": "backlog.ledger.honest.v1",
            "ledger_remaining": 3,
            "rescan_remaining": 4,
            "claimed_ok": False,
            "recorded_state": "BACKLOG_LEDGER_RESCAN_MISMATCH",
            "fixture_version": "v1",
        },
        "expect": "BACKLOG_LEDGER_RESCAN_MISMATCH",
    },
    {
        "case_id": "GEO-LEDGER-RESCAN-ALIGNED",
        "receipt": {
            "kind": "ledger_rescan_aligned",
            "fixture_id": "backlog.ledger.aligned.v1",
            "ledger_remaining": 2,
            "rescan_remaining": 2,
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["BACKLOG_LEDGER_RESCAN_MISMATCH"],
            "fixture_version": "v1",
        },
        "expect": "BACKLOG_LEDGER_RESCAN_ALIGNED",
    },
    {
        "case_id": "GEO-RECEIPT-MISMATCH-MUST-RED",
        "receipt": {
            "kind": "receipt_mismatch",
            "fixture_id": "backlog.receipt.mismatch.v1",
            "receipt_count": 9,
            "counter_value": 10,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "BACKLOG_RECEIPT_MISMATCH",
    },
    {
        "case_id": "GEO-RECEIPT-ALIGNED",
        "receipt": {
            "kind": "receipt_aligned",
            "fixture_id": "backlog.receipt.aligned.v1",
            "receipt_count": 8,
            "counter_value": 8,
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["BACKLOG_RECEIPT_MISMATCH"],
            "fixture_version": "v1",
        },
        "expect": "BACKLOG_RECEIPT_ALIGNED",
    },
    {
        "case_id": "GEO-ALL-ALIGNED",
        "receipt": {
            "kind": "all_aligned",
            "fixture_id": "backlog.aligned.v1",
            "increment_events": 6,
            "counter_value": 6,
            "echoed_backlog": 6,
            "receipt_count": 6,
            "ledger_remaining": 1,
            "rescan_remaining": 1,
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": [
                "BACKLOG_COUNTER_SKIP_ONCE",
                "BACKLOG_LEDGER_RESCAN_MISMATCH",
                "BACKLOG_RECEIPT_MISMATCH",
            ],
            "fixture_version": "v1",
        },
        "expect": "BACKLOG_ALIGNED",
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
        "version": "BACKLOG_COUNTER_SKIP_ONCE/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "地缘思考者 (naming + echo-vs-counter skip-once + ledger/rescan vs receipt question)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
