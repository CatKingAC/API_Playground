#!/usr/bin/env python3
"""RECEIPT_COLS_EQ_BOTH_POLLUTED v0.1

Peer evidence (Noteknot, EigenFlux PM + public write-up hb1231):
  A first-version receipt guard only checked that two digest columns
  were equal. If both columns were written with the same build-artifact
  polluted digest, the columns matched and the receipt looked
  consistent — but it still described the machine, not the tree.
  The stronger guard derives the tree digest from the declared commit
  itself (a commit cannot contain those build products) and compares
  that derived value to the receipt. Writing the polluted digest into
  both columns leaves the columns equal and the binding check red.

  Two reasons fire together:
    1. MEASURED_NE_COMMIT_TREE — the commit's tree is not the
       tree the receipt measured
    2. RECEIPT_COMMIT_TREE_NE_COMMIT — the receipt's own recorded
       commit-tree column does not match that commit

  Literal fault values (Noteknot self-capture):
    declared commit a228cc6, polluted digest 675c10c4 (workspace
    including install/build products), a228cc6's own tree 94740358.
  Peer implementation after the stronger arm:
    commit d4fd529, remote head 5ca5c74, suite 559/559 exit 0.
  Four published artifact digests unchanged:
    641c39b9 / b7cbb2cc / dd4d5935 / 7504bcae.

Arms (must-fail + control, paired):
  1. BOTH_POLLUTED_MUST_RED — both columns 675c10c4, claimed_ok,
     weak col-eq guard → FAIL BOTH_POLLUTED
  2. BOTH_POLLUTED_HONEST — same facts, recorded BOTH_POLLUTED
     → PASS BOTH_POLLUTED
  3. BOUND_PASS — both columns equal the commit-derived tree
     → PASS BOUND
  4. MISSING_COMMIT_MUST_RED — no declared commit, claimed_ok
     → FAIL UNKNOWN
  5. MISSING_COMMIT_HONEST — no declared commit, recorded UNKNOWN
     → PASS UNKNOWN
  6. COLLAPSED_AS_COL_EQ_OK — both polluted, recorded COL_EQ
     because the columns matched → FAIL BOTH_POLLUTED
  7. DERIVE_UNRESOLVABLE_MUST_RED — commit present but the
     independently derived tree is missing, claimed_ok → FAIL UNKNOWN
  8. DERIVE_UNRESOLVABLE_HONEST — same, recorded UNKNOWN
     → PASS UNKNOWN

analyze_only. Stdlib only.
Credit: Noteknot (self-landed stronger arm: derive tree from
        commit, not column-equality; d4fd529 / 5ca5c74 / 559/559);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any

NOTEKNOT_COMMIT = "a228cc6"
POLLUTED_DIGEST = "675c10c4"
COMMIT_OWN_TREE = "94740358"

COMMON_META = {
    "synthetic": True,
    "analyze_only": True,
    "source": "noteknot-hb1231-both-polluted-cols",
    "peer_impl_commit": "d4fd529",
    "peer_remote_head": "5ca5c74",
    "peer_suite": "559/559",
    "artifact_digests": ["641c39b9", "b7cbb2cc", "dd4d5935", "7504bcae"],
}


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    declared = receipt.get("declared_commit")
    measured = receipt.get("measured_tree_digest")
    recorded_commit_tree = receipt.get("recorded_commit_tree_digest")
    commit_derived = receipt.get("commit_derived_tree_digest")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state")
    guard = receipt.get("guard_mode") or "unspecified"

    if not declared:
        detail = {
            "declared_commit": declared,
            "measured_tree_digest": measured,
            "note": "receipt has no declared commit from which to derive a tree",
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

    if commit_derived is None:
        detail = {
            "declared_commit": declared,
            "measured_tree_digest": measured,
            "recorded_commit_tree_digest": recorded_commit_tree,
            "note": "commit tree could not be derived independently; treat as invalid",
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

    columns_equal = measured == recorded_commit_tree
    measured_ne_derived = measured != commit_derived
    recorded_col_ne_derived = recorded_commit_tree != commit_derived
    reasons: list[str] = []
    if measured_ne_derived:
        reasons.append("MEASURED_NE_COMMIT_TREE")
    if recorded_col_ne_derived:
        reasons.append("RECEIPT_COMMIT_TREE_NE_COMMIT")

    detail = {
        "declared_commit": declared,
        "measured_tree_digest": measured,
        "recorded_commit_tree_digest": recorded_commit_tree,
        "commit_derived_tree_digest": commit_derived,
        "columns_equal": columns_equal,
        "guard_mode": guard,
        "reasons": reasons,
    }

    if reasons:
        reason = "BOTH_POLLUTED" if columns_equal else "UNBOUND"
        if recorded == reason and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": reason,
                "detail": {**detail, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": reason,
            "detail": {**detail, "claimed_ok": claimed_ok, "recorded_state": recorded},
        }

    return {
        "judge": "PASS",
        "reason_code": "BOUND",
        "detail": {**detail, "bound": True},
    }


FIXTURES = [
    {
        "case_id": "RCEB-BOTH-POLLUTED-MUST-RED",
        "receipt": {
            "kind": "both_polluted_must_red",
            "fixture_id": "receipt.cols.eq.both.polluted.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": POLLUTED_DIGEST,
            "recorded_commit_tree_digest": POLLUTED_DIGEST,
            "commit_derived_tree_digest": COMMIT_OWN_TREE,
            "guard_mode": "col_eq_only",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "BOTH_POLLUTED",
    },
    {
        "case_id": "RCEB-BOTH-POLLUTED-HONEST",
        "receipt": {
            "kind": "both_polluted_honest",
            "fixture_id": "receipt.cols.eq.both.polluted.honest.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": POLLUTED_DIGEST,
            "recorded_commit_tree_digest": POLLUTED_DIGEST,
            "commit_derived_tree_digest": COMMIT_OWN_TREE,
            "guard_mode": "derive_tree_from_commit",
            "claimed_ok": False,
            "recorded_state": "BOTH_POLLUTED",
            **COMMON_META,
        },
        "expect": "BOTH_POLLUTED",
    },
    {
        "case_id": "RCEB-BOUND-PASS",
        "receipt": {
            "kind": "bound_pass",
            "fixture_id": "receipt.cols.eq.both.polluted.bound.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": COMMIT_OWN_TREE,
            "recorded_commit_tree_digest": COMMIT_OWN_TREE,
            "commit_derived_tree_digest": COMMIT_OWN_TREE,
            "guard_mode": "derive_tree_from_commit",
            "claimed_ok": True,
            "must_not_trip": ["BOTH_POLLUTED", "UNBOUND", "UNKNOWN"],
            **COMMON_META,
        },
        "expect": "BOUND",
    },
    {
        "case_id": "RCEB-MISSING-COMMIT-MUST-RED",
        "receipt": {
            "kind": "missing_commit_must_red",
            "fixture_id": "receipt.cols.eq.both.polluted.missing.v1",
            "declared_commit": None,
            "measured_tree_digest": POLLUTED_DIGEST,
            "recorded_commit_tree_digest": POLLUTED_DIGEST,
            "commit_derived_tree_digest": None,
            "guard_mode": "col_eq_only",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "RCEB-MISSING-COMMIT-HONEST",
        "receipt": {
            "kind": "missing_commit_honest",
            "fixture_id": "receipt.cols.eq.both.polluted.missing.honest.v1",
            "declared_commit": None,
            "measured_tree_digest": POLLUTED_DIGEST,
            "recorded_commit_tree_digest": POLLUTED_DIGEST,
            "commit_derived_tree_digest": None,
            "guard_mode": "col_eq_only",
            "claimed_ok": False,
            "recorded_state": "UNKNOWN",
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "RCEB-COLLAPSED-AS-COL-EQ-OK",
        "receipt": {
            "kind": "collapsed_as_col_eq_ok",
            "fixture_id": "receipt.cols.eq.both.polluted.collapsed.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": POLLUTED_DIGEST,
            "recorded_commit_tree_digest": POLLUTED_DIGEST,
            "commit_derived_tree_digest": COMMIT_OWN_TREE,
            "guard_mode": "col_eq_only",
            "claimed_ok": True,
            "recorded_state": "COL_EQ",
            **COMMON_META,
        },
        "expect": "BOTH_POLLUTED",
    },
    {
        "case_id": "RCEB-DERIVE-UNRESOLVABLE-MUST-RED",
        "receipt": {
            "kind": "derive_unresolvable_must_red",
            "fixture_id": "receipt.cols.eq.both.polluted.unresolvable.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": POLLUTED_DIGEST,
            "recorded_commit_tree_digest": POLLUTED_DIGEST,
            "commit_derived_tree_digest": None,
            "guard_mode": "derive_tree_from_commit",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "RCEB-DERIVE-UNRESOLVABLE-HONEST",
        "receipt": {
            "kind": "derive_unresolvable_honest",
            "fixture_id": "receipt.cols.eq.both.polluted.unresolvable.honest.v1",
            "declared_commit": NOTEKNOT_COMMIT,
            "measured_tree_digest": POLLUTED_DIGEST,
            "recorded_commit_tree_digest": POLLUTED_DIGEST,
            "commit_derived_tree_digest": None,
            "guard_mode": "derive_tree_from_commit",
            "claimed_ok": False,
            "recorded_state": "UNKNOWN",
            **COMMON_META,
        },
        "expect": "UNKNOWN",
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
        "version": "RECEIPT_COLS_EQ_BOTH_POLLUTED/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "Noteknot (stronger arm: derive tree from commit, not column-equality; d4fd529 / 5ca5c74 / 559/559)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
