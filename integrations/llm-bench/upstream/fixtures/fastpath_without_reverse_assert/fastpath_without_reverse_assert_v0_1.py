#!/usr/bin/env python3
"""FASTPATH_WITHOUT_REVERSE_ASSERT v0.1

Peer evidence (xiaoyou的dsh / DeepSeek-Harness, EigenFlux feed hb0626):
  Testing detectors with only positive samples yields false confidence —
  a detector that always returns red would still "pass" such a suite.
  Three structural fixes proposed:
    (1) negative controls on every fixture;
    (2) reverse assertions must themselves be falsifiable via a concrete
        counter-example (not a tautology);
    (3) cache/hash domains need bidirectional checks (A→B and B→A), not
        a one-way fastpath digest that claims OK.

  Open owe FASTPATH_WITHOUT_REVERSE_ASSERT: a forward/fastpath assert
  (summary digest match, status green, short-circuit OK) without a
  reverse assert that a known-bad sample would fail → must RED, never PASS.

Arms:
  1. FASTPATH_WITHOUT_REVERSE_ASSERT — forward_ok + reverse not run, claimed OK → FAIL
  2. FASTPATH_REVERSE_HONEST — reverse missing recorded FASTPATH_WITHOUT_REVERSE_ASSERT → PASS
  3. FASTPATH_WITH_REVERSE_NEGCTRL — forward+reverse both ran+pass → PASS (must_not_trip)
  4. REVERSE_ASSERT_UNFALSIFIABLE — reverse ran but no counterexample defined, claimed OK → FAIL
  5. REVERSE_COUNTEREXAMPLE_TRIPS — known-bad counterexample trips reverse → PASS
  6. BIDIR_HASH_ONE_WAY — only A→B digest claimed OK → FAIL
  7. BIDIR_HASH_BOTH_WAYS — A→B and B→A → PASS (must_not_trip)
  8. POSITIVE_ONLY_DETECTOR — positives only / zero negctrl rows claimed OK → FAIL

analyze_only. Stdlib only.
Credit: xiaoyou的dsh (negctrl + reverse-falsifiable + bidir hash evidence);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state") or receipt.get("reason_code")
    forward_ok = receipt.get("forward_assert_ok") is True
    reverse_ran = receipt.get("reverse_assert_ran") is True
    reverse_ok = receipt.get("reverse_assert_ok") is True
    counter_defined = receipt.get("counterexample_defined") is True
    counter_trips = receipt.get("counterexample_trips_reverse") is True
    tripped = list(receipt.get("tripped_codes") or [])

    # Arms 6/7 — bidirectional hash
    if kind in ("bidir_one_way", "bidir_both") or receipt.get("check") == "bidir_hash":
        a2b = receipt.get("digest_a_to_b_ok") is True
        b2a = receipt.get("digest_b_to_a_ok") is True
        if a2b and not b2a and claimed_ok and recorded != "BIDIR_HASH_ONE_WAY":
            return {
                "judge": "FAIL",
                "reason_code": "BIDIR_HASH_ONE_WAY",
                "detail": {"a2b": a2b, "b2a": b2a},
            }
        if a2b and b2a:
            if "BIDIR_HASH_ONE_WAY" in tripped or "FASTPATH_WITHOUT_REVERSE_ASSERT" in tripped:
                return {
                    "judge": "FAIL",
                    "reason_code": "BIDIR_HASH_ONE_WAY",
                    "detail": {"note": "must_not_trip on both-ways digest"},
                }
            return {
                "judge": "PASS",
                "reason_code": "BIDIR_HASH_BOTH_WAYS",
                "detail": {"a2b": True, "b2a": True},
            }
        if a2b and not b2a and recorded == "BIDIR_HASH_ONE_WAY" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "BIDIR_HASH_ONE_WAY",
                "detail": {"honest": True},
            }

    # Arm 8 — positive-only detector
    if kind == "positive_only" or receipt.get("check") == "pos_only":
        n_pos = int(receipt.get("n_positive_samples") or 0)
        n_neg = int(receipt.get("n_negctrl_samples") or 0)
        if n_pos > 0 and n_neg == 0 and claimed_ok and recorded != "POSITIVE_ONLY_DETECTOR":
            return {
                "judge": "FAIL",
                "reason_code": "POSITIVE_ONLY_DETECTOR",
                "detail": {"n_positive": n_pos, "n_negctrl": n_neg},
            }
        if n_pos > 0 and n_neg == 0 and recorded == "POSITIVE_ONLY_DETECTOR" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "POSITIVE_ONLY_DETECTOR",
                "detail": {"honest": True},
            }
        if n_pos > 0 and n_neg > 0:
            return {
                "judge": "PASS",
                "reason_code": "POSITIVE_ONLY_DETECTOR",
                "detail": {"note": "has_negctrl", "n_negctrl": n_neg},
            }

    # Arms 4/5 — reverse falsifiability
    if kind in ("reverse_unfalsifiable", "reverse_counter_trips") or receipt.get(
        "check"
    ) == "reverse_falsifiable":
        if reverse_ran and not counter_defined and claimed_ok and recorded != "REVERSE_ASSERT_UNFALSIFIABLE":
            return {
                "judge": "FAIL",
                "reason_code": "REVERSE_ASSERT_UNFALSIFIABLE",
                "detail": {"reverse_ran": True, "counterexample_defined": False},
            }
        if (
            reverse_ran
            and counter_defined
            and counter_trips
            and not claimed_ok
            and recorded in ("REVERSE_ASSERT_UNFALSIFIABLE", "FASTPATH_WITHOUT_REVERSE_ASSERT", "COUNTEREXAMPLE_TRIPPED")
        ):
            return {
                "judge": "PASS",
                "reason_code": "REVERSE_COUNTEREXAMPLE_TRIPS",
                "detail": {"counterexample_trips_reverse": True},
            }
        if reverse_ran and not counter_defined and recorded == "REVERSE_ASSERT_UNFALSIFIABLE" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "REVERSE_ASSERT_UNFALSIFIABLE",
                "detail": {"honest": True},
            }

    # Arms 1/2/3 — fastpath without reverse
    if kind in (
        "fastpath_no_reverse",
        "fastpath_honest",
        "fastpath_with_reverse",
    ) or receipt.get("check") == "fastpath_reverse":
        if forward_ok and not reverse_ran and claimed_ok and recorded not in (
            "FASTPATH_WITHOUT_REVERSE_ASSERT",
        ):
            return {
                "judge": "FAIL",
                "reason_code": "FASTPATH_WITHOUT_REVERSE_ASSERT",
                "detail": {"forward_ok": True, "reverse_assert_ran": False},
            }
        if (
            forward_ok
            and not reverse_ran
            and not claimed_ok
            and recorded == "FASTPATH_WITHOUT_REVERSE_ASSERT"
        ):
            return {
                "judge": "PASS",
                "reason_code": "FASTPATH_WITHOUT_REVERSE_ASSERT",
                "detail": {"honest": True},
            }
        if forward_ok and reverse_ran and reverse_ok:
            if "FASTPATH_WITHOUT_REVERSE_ASSERT" in tripped:
                return {
                    "judge": "FAIL",
                    "reason_code": "FASTPATH_WITHOUT_REVERSE_ASSERT",
                    "detail": {"note": "must_not_trip when reverse ran+ok"},
                }
            return {
                "judge": "PASS",
                "reason_code": "FASTPATH_WITH_REVERSE_NEGCTRL",
                "detail": {"forward_ok": True, "reverse_ok": True},
            }

    return {
        "judge": "FAIL",
        "reason_code": "UNDECIDABLE",
        "detail": {"kind": kind},
    }


FIXTURES = [
    {
        "case_id": "DSH-FASTPATH-NO-REVERSE-MUST-RED",
        "receipt": {
            "kind": "fastpath_no_reverse",
            "fixture_id": "fastpath.noreverse.v1",
            "forward_assert_ok": True,
            "reverse_assert_ran": False,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "FASTPATH_WITHOUT_REVERSE_ASSERT",
    },
    {
        "case_id": "DSH-FASTPATH-REVERSE-HONEST",
        "receipt": {
            "kind": "fastpath_honest",
            "fixture_id": "fastpath.noreverse.v1.honest",
            "forward_assert_ok": True,
            "reverse_assert_ran": False,
            "claimed_ok": False,
            "recorded_state": "FASTPATH_WITHOUT_REVERSE_ASSERT",
            "fixture_version": "v1",
        },
        "expect": "FASTPATH_WITHOUT_REVERSE_ASSERT",
    },
    {
        "case_id": "DSH-FASTPATH-WITH-REVERSE-NEGCTRL",
        "receipt": {
            "kind": "fastpath_with_reverse",
            "fixture_id": "fastpath.withreverse.v1",
            "forward_assert_ok": True,
            "reverse_assert_ran": True,
            "reverse_assert_ok": True,
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["FASTPATH_WITHOUT_REVERSE_ASSERT"],
            "fixture_version": "v1",
        },
        "expect": "FASTPATH_WITH_REVERSE_NEGCTRL",
    },
    {
        "case_id": "DSH-REVERSE-UNFALSIFIABLE-MUST-RED",
        "receipt": {
            "kind": "reverse_unfalsifiable",
            "fixture_id": "reverse.unfalsifiable.v1",
            "forward_assert_ok": True,
            "reverse_assert_ran": True,
            "counterexample_defined": False,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "REVERSE_ASSERT_UNFALSIFIABLE",
    },
    {
        "case_id": "DSH-REVERSE-COUNTEREXAMPLE-TRIPS",
        "receipt": {
            "kind": "reverse_counter_trips",
            "fixture_id": "reverse.counter.v1",
            "forward_assert_ok": True,
            "reverse_assert_ran": True,
            "counterexample_defined": True,
            "counterexample_trips_reverse": True,
            "claimed_ok": False,
            "recorded_state": "COUNTEREXAMPLE_TRIPPED",
            "fixture_version": "v1",
        },
        "expect": "REVERSE_COUNTEREXAMPLE_TRIPS",
    },
    {
        "case_id": "DSH-BIDIR-HASH-ONE-WAY-MUST-RED",
        "receipt": {
            "kind": "bidir_one_way",
            "fixture_id": "bidir.oneway.v1",
            "digest_a_to_b_ok": True,
            "digest_b_to_a_ok": False,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "BIDIR_HASH_ONE_WAY",
    },
    {
        "case_id": "DSH-BIDIR-HASH-BOTH-WAYS",
        "receipt": {
            "kind": "bidir_both",
            "fixture_id": "bidir.both.v1",
            "digest_a_to_b_ok": True,
            "digest_b_to_a_ok": True,
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["BIDIR_HASH_ONE_WAY", "FASTPATH_WITHOUT_REVERSE_ASSERT"],
            "fixture_version": "v1",
        },
        "expect": "BIDIR_HASH_BOTH_WAYS",
    },
    {
        "case_id": "DSH-POSITIVE-ONLY-DETECTOR-MUST-RED",
        "receipt": {
            "kind": "positive_only",
            "fixture_id": "posonly.detector.v1",
            "n_positive_samples": 12,
            "n_negctrl_samples": 0,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "POSITIVE_ONLY_DETECTOR",
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
        "version": "FASTPATH_WITHOUT_REVERSE_ASSERT/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "xiaoyou的dsh (negctrl + reverse-falsifiable + bidir hash evidence)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
