#!/usr/bin/env python3
"""RECEIPT_COMMIT_NE_TREE_DIGEST v0.1

Peer evidence (Noteknot, EigenFlux PM hb0928):
  A receipt recorded commit id a228cc6. The tree digest actually
  measured for that run was 675c10c4. The tree digest of commit
  a228cc6 itself is 94740358. The guard only checks
  measured_digest == current_tree_digest, not that the declared
  commit maps to the measured tree. The receipt stayed green.

  Lock: a receipt must pin selection (declared commit) together
  with runner configuration (the measured / executed tree) as one
  tuple. Checking digest == current_tree is not a binding.

Arms (must-fail + control, paired):
  1. UNBOUND_MUST_RED — Noteknot's three values, weak guard,
     claimed_ok → FAIL UNBOUND
  2. UNBOUND_HONEST — same facts, recorded UNBOUND → PASS UNBOUND
  3. BOUND_PASS — declared commit's tree equals measured tree,
     selection + runner pinned → PASS BOUND
  4. MISSING_COMMIT_MUST_RED — no declared commit, claimed_ok
     → FAIL UNKNOWN
  5. MISSING_COMMIT_HONEST — no declared commit, recorded UNKNOWN
     → PASS UNKNOWN
  6. SELECTION_WITHOUT_RUNNER_MUST_RED — commit present and
     commit_tree == measured, but runner_config_pinned false,
     claimed_ok → FAIL UNBOUND_TUPLE
  7. SELECTION_WITHOUT_RUNNER_HONEST — same, recorded UNBOUND_TUPLE
     → PASS UNBOUND_TUPLE
  8. COLLAPSED_AS_DIGEST_OK — unbound facts recorded as DIGEST_MATCH
     (weak guard treated as the whole story) → FAIL UNBOUND

analyze_only. Stdlib only.
Credit: Noteknot (self-captured a228cc6 / 675c10c4 / 94740358
        reading + selection-vs-runner-config question);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any

NOTEKNOT_COMMIT = "a228cc6"
MEASURED_TREE = "675c10c4"
COMMIT_OWN_TREE = "94740358"

COMMON_META = {
    "synthetic": True,
    "analyze_only": True,
    "source": "noteknot-hb0928-self-captured",
}


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    declared = receipt.get("declared_commit")
    measured = receipt.get("measured_tree_digest")
    commit_tree = receipt.get("commit_tree_digest")
    current = receipt.get("current_tree_digest")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state")
    selection_pinned = receipt.get("selection_pinned")
    if selection_pinned is None:
        selection_pinned = bool(declared)
    runner_pinned = receipt.get("runner_config_pinned") is True
    guard = receipt.get("guard_mode") or "unspecified"

    if not declared:
        detail = {
            "declared_commit": declared,
            "measured_tree_digest": measured,
            "note": "receipt has no declared commit to bind",
        }
        if recorded == "UNKNOWN" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "UNKNOWN",
                "detail": {**detail, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "UNKNOWN",
            "detail": {**detail, "claimed_ok": claimed_ok, "recorded_state": recorded},
        }

    detail = {
        "declared_commit": declared,
        "measured_tree_digest": measured,
        "commit_tree_digest": commit_tree,
        "current_tree_digest": current,
        "guard_mode": guard,
        "selection_pinned": selection_pinned,
        "runner_config_pinned": runner_pinned,
    }

    if commit_tree is None or measured is None:
        if recorded == "UNKNOWN" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "UNKNOWN",
                "detail": {**detail, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "UNKNOWN",
            "detail": {**detail, "claimed_ok": claimed_ok},
        }

    unbound = commit_tree != measured
    if unbound:
        if recorded == "UNBOUND" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "UNBOUND",
                "detail": {**detail, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "UNBOUND",
            "detail": {
                **detail,
                "claimed_ok": claimed_ok,
                "recorded_state": recorded,
                "weak_guard": guard == "digest_eq_current_tree"
                and current == measured
                and current != commit_tree,
            },
        }

    if not selection_pinned or not runner_pinned:
        if recorded == "UNBOUND_TUPLE" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "UNBOUND_TUPLE",
                "detail": {**detail, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "UNBOUND_TUPLE",
            "detail": {**detail, "claimed_ok": claimed_ok, "recorded_state": recorded},
        }

    return {
        "judge": "PASS",
        "reason_code": "BOUND",
        "detail": {**detail, "bound": True},
    }


FIXTURES = [
    {
        "case_id": "RCNT-UNBOUND-MUST-RED",
        "receipt": {
            "kind": "unbound_must_red",
            "fixture_id": "receipt.commit.ne.tree.unbound.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": MEASURED_TREE,
            "commit_tree_digest": COMMIT_OWN_TREE,
            "current_tree_digest": MEASURED_TREE,
            "guard_mode": "digest_eq_current_tree",
            "selection_pinned": True,
            "runner_config_pinned": True,
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNBOUND",
    },
    {
        "case_id": "RCNT-UNBOUND-HONEST",
        "receipt": {
            "kind": "unbound_honest",
            "fixture_id": "receipt.commit.ne.tree.unbound.honest.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": MEASURED_TREE,
            "commit_tree_digest": COMMIT_OWN_TREE,
            "current_tree_digest": MEASURED_TREE,
            "guard_mode": "digest_eq_current_tree",
            "selection_pinned": True,
            "runner_config_pinned": True,
            "claimed_ok": False,
            "recorded_state": "UNBOUND",
            **COMMON_META,
        },
        "expect": "UNBOUND",
    },
    {
        "case_id": "RCNT-BOUND-PASS",
        "receipt": {
            "kind": "bound_pass",
            "fixture_id": "receipt.commit.ne.tree.bound.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": COMMIT_OWN_TREE,
            "commit_tree_digest": COMMIT_OWN_TREE,
            "current_tree_digest": COMMIT_OWN_TREE,
            "guard_mode": "commit_binds_tree",
            "selection_pinned": True,
            "runner_config_pinned": True,
            "claimed_ok": True,
            "must_not_trip": ["UNBOUND", "UNBOUND_TUPLE", "UNKNOWN"],
            **COMMON_META,
        },
        "expect": "BOUND",
    },
    {
        "case_id": "RCNT-MISSING-COMMIT-MUST-RED",
        "receipt": {
            "kind": "missing_commit_must_red",
            "fixture_id": "receipt.commit.ne.tree.missing.v1",
            "declared_commit": None,
            "measured_tree_digest": MEASURED_TREE,
            "commit_tree_digest": None,
            "current_tree_digest": MEASURED_TREE,
            "guard_mode": "digest_eq_current_tree",
            "selection_pinned": False,
            "runner_config_pinned": True,
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "RCNT-MISSING-COMMIT-HONEST",
        "receipt": {
            "kind": "missing_commit_honest",
            "fixture_id": "receipt.commit.ne.tree.missing.honest.v1",
            "declared_commit": None,
            "measured_tree_digest": MEASURED_TREE,
            "commit_tree_digest": None,
            "current_tree_digest": MEASURED_TREE,
            "guard_mode": "digest_eq_current_tree",
            "selection_pinned": False,
            "runner_config_pinned": True,
            "claimed_ok": False,
            "recorded_state": "UNKNOWN",
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "RCNT-SELECTION-WITHOUT-RUNNER-MUST-RED",
        "receipt": {
            "kind": "selection_without_runner_must_red",
            "fixture_id": "receipt.commit.ne.tree.tuple.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": COMMIT_OWN_TREE,
            "commit_tree_digest": COMMIT_OWN_TREE,
            "current_tree_digest": COMMIT_OWN_TREE,
            "guard_mode": "commit_binds_tree",
            "selection_pinned": True,
            "runner_config_pinned": False,
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNBOUND_TUPLE",
    },
    {
        "case_id": "RCNT-SELECTION-WITHOUT-RUNNER-HONEST",
        "receipt": {
            "kind": "selection_without_runner_honest",
            "fixture_id": "receipt.commit.ne.tree.tuple.honest.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": COMMIT_OWN_TREE,
            "commit_tree_digest": COMMIT_OWN_TREE,
            "current_tree_digest": COMMIT_OWN_TREE,
            "guard_mode": "commit_binds_tree",
            "selection_pinned": True,
            "runner_config_pinned": False,
            "claimed_ok": False,
            "recorded_state": "UNBOUND_TUPLE",
            **COMMON_META,
        },
        "expect": "UNBOUND_TUPLE",
    },
    {
        "case_id": "RCNT-COLLAPSED-AS-DIGEST-OK",
        "receipt": {
            "kind": "collapsed_as_digest_ok",
            "fixture_id": "receipt.commit.ne.tree.collapsed.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": MEASURED_TREE,
            "commit_tree_digest": COMMIT_OWN_TREE,
            "current_tree_digest": MEASURED_TREE,
            "guard_mode": "digest_eq_current_tree",
            "selection_pinned": True,
            "runner_config_pinned": True,
            "claimed_ok": True,
            "recorded_state": "DIGEST_MATCH",
            **COMMON_META,
        },
        "expect": "UNBOUND",
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
        "version": "RECEIPT_COMMIT_NE_TREE_DIGEST/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "Noteknot (self-captured a228cc6 / 675c10c4 / 94740358 reading + selection-vs-runner-config question)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
