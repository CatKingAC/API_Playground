#!/usr/bin/env python3
"""HANG_GREEN_ZERO_COOLDOWN_SPIN v0.1

Peer evidence (R13113456196 / Issue #3, SEMANTIC_COLLISION):
  Existence probes (process alive, heartbeat, HTTP 200) stay green while the
  main advance loop spins forever when refire/cooldown read is 0:
    while currElapsed > refireDelay:
        currElapsed -= refireDelay  # subtracting 0 never exits
  Monitoring speaks existence semantics; the fault needs progress semantics.
  Sharing one "healthy" label across both = SEMANTIC_COLLISION.

  Fix vectors: clamp read with floor > 0 (e.g. 0.05); filter zero-cooldown
  sources at load; negctrl floor=0 must reproduce hang (RED).

Arms:
  1. HANG_GREEN_ZERO_COOLDOWN_SPIN — zero cooldown spin, existence green, claimed_ok → FAIL
  2. HANG_GREEN_ZERO_COOLDOWN_SPIN — same defect, honestly recorded → PASS
  3. COOLDOWN_FLOOR_POS_PROGRESS — floor>0, loop advances → PASS
  4. FLOOR_ZERO_NEGCTRL — floor=0 hang reproduced, falsely green → FAIL
  5. EXISTENCE_ONLY_HEALTH_GREEN — existence green, progress stuck, claimed_ok → FAIL
  6. PROGRESS_AND_EXISTENCE_BOTH_OK — both satisfied → PASS (must_not_trip)
  7. SEMANTIC_COLLISION — collapsed existence/progress label while spinning → FAIL
  8. SEMANTIC_COLLISION — honest split labels on hang → PASS

analyze_only. Stdlib only.
Credit: R13113456196 (Issue #3 structure + SEMANTIC_COLLISION);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any

GREEN = frozenset({"GREEN", "OK", "PASS", "HEALTHY", "200"})


def _existence_all_green(receipt: dict[str, Any]) -> bool:
    probes = receipt.get("existence_probes") or {}
    return (
        probes.get("process_alive") is True
        and probes.get("heartbeat_ok") is True
        and probes.get("http_health") is True
    )


def _progress_advancing(receipt: dict[str, Any]) -> bool:
    if receipt.get("main_loop_advancing") is not True:
        return False
    if receipt.get("spin_detected") is True:
        return False
    if receipt.get("ui_load_complete") is False:
        return False
    return True


def _zero_cooldown_spin(receipt: dict[str, Any]) -> bool:
    read = receipt.get("refire_delay_read")
    if read is None:
        read = receipt.get("cooldown_read")
    floor = receipt.get("cooldown_floor")
    if floor is not None and floor > 0:
        return False
    if read != 0:
        return False
    return receipt.get("spin_detected") is True and not _progress_advancing(receipt)


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state") or receipt.get("reason_code")
    tripped = list(receipt.get("tripped_codes") or [])

    # Arms 7/8 — SEMANTIC_COLLISION (shared healthy label)
    if kind in ("semantic_collision", "semantic_collision_honest") or receipt.get("check") == "semantic_collision":
        shared = receipt.get("shared_health_label")
        spin = receipt.get("spin_detected") is True
        progress_stuck = not _progress_advancing(receipt)
        existence_green = _existence_all_green(receipt)
        if (
            shared
            and spin
            and progress_stuck
            and existence_green
            and claimed_ok
            and recorded != "SEMANTIC_COLLISION"
        ):
            return {
                "judge": "FAIL",
                "reason_code": "SEMANTIC_COLLISION",
                "detail": {"shared_label": shared, "spin": True},
            }
        if (
            recorded == "SEMANTIC_COLLISION"
            and not claimed_ok
            and spin
            and receipt.get("progress_label") != receipt.get("existence_label")
        ):
            return {
                "judge": "PASS",
                "reason_code": "SEMANTIC_COLLISION",
                "detail": {"honest": True, "labels_split": True},
            }

    # Arms 5/6 — existence vs progress pairing
    if kind in ("existence_only_green", "progress_and_existence_ok") or receipt.get("check") == "existence_progress":
        existence_green = _existence_all_green(receipt)
        progress_ok = _progress_advancing(receipt)
        must_not = receipt.get("must_not_trip") or []
        if existence_green and not progress_ok and claimed_ok and recorded != "EXISTENCE_ONLY_HEALTH_GREEN":
            return {
                "judge": "FAIL",
                "reason_code": "EXISTENCE_ONLY_HEALTH_GREEN",
                "detail": {"existence_green": True, "progress_ok": False},
            }
        if existence_green and progress_ok:
            for code in must_not:
                if code in tripped:
                    return {
                        "judge": "FAIL",
                        "reason_code": "PROGRESS_AND_EXISTENCE_BOTH_OK",
                        "detail": {"note": f"must_not_trip violated: {code}"},
                    }
            return {
                "judge": "PASS",
                "reason_code": "PROGRESS_AND_EXISTENCE_BOTH_OK",
                "detail": {"existence_green": True, "progress_ok": True},
            }

    # Arm 4 — floor=0 negative control
    if kind == "floor_zero_negctrl" or receipt.get("check") == "cooldown_floor_negctrl":
        floor = receipt.get("cooldown_floor")
        if floor == 0 and _zero_cooldown_spin(receipt) and claimed_ok and recorded != "FLOOR_ZERO_NEGCTRL":
            return {
                "judge": "FAIL",
                "reason_code": "FLOOR_ZERO_NEGCTRL",
                "detail": {"floor": 0, "negctrl_must_red": True},
            }
        if floor == 0 and _zero_cooldown_spin(receipt) and recorded == "FLOOR_ZERO_NEGCTRL" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "FLOOR_ZERO_NEGCTRL",
                "detail": {"honest_negctrl": True},
            }

    # Arm 3 — floor>0 progress
    if kind == "floor_pos_progress" or receipt.get("check") == "cooldown_floor":
        floor = receipt.get("cooldown_floor")
        if floor is not None and floor > 0 and _progress_advancing(receipt):
            if "HANG_GREEN_ZERO_COOLDOWN_SPIN" in tripped or "FLOOR_ZERO_NEGCTRL" in tripped:
                return {
                    "judge": "FAIL",
                    "reason_code": "COOLDOWN_FLOOR_POS_PROGRESS",
                    "detail": {"note": "must_not_trip on healthy floor>0 path"},
                }
            return {
                "judge": "PASS",
                "reason_code": "COOLDOWN_FLOOR_POS_PROGRESS",
                "detail": {"floor": floor, "advancing": True},
            }

    # Arms 1/2 — primary hang defect
    if kind in ("hang_green_spin", "hang_honest") or receipt.get("check") == "zero_cooldown_spin":
        if _zero_cooldown_spin(receipt) and _existence_all_green(receipt):
            if claimed_ok and recorded != "HANG_GREEN_ZERO_COOLDOWN_SPIN":
                return {
                    "judge": "FAIL",
                    "reason_code": "HANG_GREEN_ZERO_COOLDOWN_SPIN",
                    "detail": {
                        "refire_delay_read": 0,
                        "existence_green": True,
                        "spin_detected": True,
                    },
                }
            if not claimed_ok and recorded == "HANG_GREEN_ZERO_COOLDOWN_SPIN":
                return {
                    "judge": "PASS",
                    "reason_code": "HANG_GREEN_ZERO_COOLDOWN_SPIN",
                    "detail": {"honest": True},
                }

    return {
        "judge": "FAIL",
        "reason_code": "UNDECIDABLE",
        "detail": {"kind": kind},
    }


FIXTURES = [
    {
        "case_id": "ISSUE3-HANG-GREEN-ZERO-COOLDOWN-SPIN-MUST-RED",
        "receipt": {
            "kind": "hang_green_spin",
            "fixture_id": "hang.green.spin.v1",
            "refire_delay_read": 0,
            "cooldown_floor": None,
            "spin_detected": True,
            "main_loop_advancing": False,
            "ui_load_complete": False,
            "existence_probes": {
                "process_alive": True,
                "heartbeat_ok": True,
                "http_health": True,
            },
            "jfr_same_frame_samples": 563,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "HANG_GREEN_ZERO_COOLDOWN_SPIN",
    },
    {
        "case_id": "ISSUE3-HANG-GREEN-ZERO-COOLDOWN-HONEST",
        "receipt": {
            "kind": "hang_honest",
            "fixture_id": "hang.honest.v1",
            "refire_delay_read": 0,
            "spin_detected": True,
            "main_loop_advancing": False,
            "ui_load_complete": False,
            "existence_probes": {
                "process_alive": True,
                "heartbeat_ok": True,
                "http_health": True,
            },
            "claimed_ok": False,
            "recorded_state": "HANG_GREEN_ZERO_COOLDOWN_SPIN",
            "fixture_version": "v1",
        },
        "expect": "HANG_GREEN_ZERO_COOLDOWN_SPIN",
    },
    {
        "case_id": "ISSUE3-COOLDOWN-FLOOR-POS-PROGRESS",
        "receipt": {
            "kind": "floor_pos_progress",
            "fixture_id": "floor.pos.v1",
            "refire_delay_read": 0,
            "cooldown_floor": 0.05,
            "refire_delay_effective": 0.05,
            "spin_detected": False,
            "main_loop_advancing": True,
            "ui_load_complete": True,
            "main_loop_index_delta": 3,
            "existence_probes": {
                "process_alive": True,
                "heartbeat_ok": True,
                "http_health": True,
            },
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["HANG_GREEN_ZERO_COOLDOWN_SPIN", "FLOOR_ZERO_NEGCTRL"],
            "fixture_version": "v1",
        },
        "expect": "COOLDOWN_FLOOR_POS_PROGRESS",
    },
    {
        "case_id": "ISSUE3-FLOOR-ZERO-NEGCTRL-MUST-RED",
        "receipt": {
            "kind": "floor_zero_negctrl",
            "fixture_id": "floor.zero.negctrl.v1",
            "refire_delay_read": 0,
            "cooldown_floor": 0,
            "spin_detected": True,
            "main_loop_advancing": False,
            "ui_load_complete": False,
            "existence_probes": {
                "process_alive": True,
                "heartbeat_ok": True,
                "http_health": True,
            },
            "claimed_ok": True,
            "reported_state": "GREEN",
            "fixture_version": "v1",
        },
        "expect": "FLOOR_ZERO_NEGCTRL",
    },
    {
        "case_id": "ISSUE3-EXISTENCE-ONLY-HEALTH-GREEN-MUST-RED",
        "receipt": {
            "kind": "existence_only_green",
            "fixture_id": "existence.only.v1",
            "check": "existence_progress",
            "refire_delay_read": 0,
            "spin_detected": True,
            "main_loop_advancing": False,
            "ui_load_complete": False,
            "existence_probes": {
                "process_alive": True,
                "heartbeat_ok": True,
                "http_health": True,
            },
            "claimed_ok": True,
            "reported_state": "HEALTHY",
            "fixture_version": "v1",
        },
        "expect": "EXISTENCE_ONLY_HEALTH_GREEN",
    },
    {
        "case_id": "ISSUE3-PROGRESS-AND-EXISTENCE-BOTH-OK",
        "receipt": {
            "kind": "progress_and_existence_ok",
            "fixture_id": "progress.existence.ok.v1",
            "check": "existence_progress",
            "refire_delay_read": 0.05,
            "cooldown_floor": 0.05,
            "spin_detected": False,
            "main_loop_advancing": True,
            "ui_load_complete": True,
            "existence_probes": {
                "process_alive": True,
                "heartbeat_ok": True,
                "http_health": True,
            },
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": [
                "HANG_GREEN_ZERO_COOLDOWN_SPIN",
                "EXISTENCE_ONLY_HEALTH_GREEN",
                "SEMANTIC_COLLISION",
            ],
            "fixture_version": "v1",
        },
        "expect": "PROGRESS_AND_EXISTENCE_BOTH_OK",
    },
    {
        "case_id": "ISSUE3-SEMANTIC-COLLISION-MUST-RED",
        "receipt": {
            "kind": "semantic_collision",
            "fixture_id": "semantic.collision.v1",
            "shared_health_label": "GREEN",
            "existence_label": "GREEN",
            "progress_label": "GREEN",
            "spin_detected": True,
            "main_loop_advancing": False,
            "ui_load_complete": False,
            "existence_probes": {
                "process_alive": True,
                "heartbeat_ok": True,
                "http_health": True,
            },
            "claimed_ok": True,
            "reported_state": "GREEN",
            "fixture_version": "v1",
        },
        "expect": "SEMANTIC_COLLISION",
    },
    {
        "case_id": "ISSUE3-SEMANTIC-COLLISION-HONEST",
        "receipt": {
            "kind": "semantic_collision_honest",
            "fixture_id": "semantic.collision.honest.v1",
            "existence_label": "GREEN",
            "progress_label": "STUCK_SPIN",
            "spin_detected": True,
            "main_loop_advancing": False,
            "ui_load_complete": False,
            "existence_probes": {
                "process_alive": True,
                "heartbeat_ok": True,
                "http_health": True,
            },
            "claimed_ok": False,
            "recorded_state": "SEMANTIC_COLLISION",
            "fixture_version": "v1",
        },
        "expect": "SEMANTIC_COLLISION",
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
        "version": "HANG_GREEN_ZERO_COOLDOWN_SPIN/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "R13113456196 (Issue #3 — HANG_GREEN_ZERO_COOLDOWN_SPIN / SEMANTIC_COLLISION)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
