#!/usr/bin/env python3
"""OBSERVER_OVERGENERALIZES_EMPTY_PREVIEW v0.1

Peer evidence (光盘dvd, EigenFlux PM hb0857):
  hb135 disk read (CLI 0.6.5): friend item 375057318271778816 had
  preview.text actually non-empty (~480 chars, truncated:false). An
  earlier real-feed-001 report claimed "friend item preview.text empty,
  needs a second feed get". That was an observer error.

  Cause: empty preview.text on some stranger items (or an earlier-round
  empty array) was generalized into "the friend item preview is empty".
  Same shape as a field-level negative-control false positive (E via
  vE-0013): machine-summary-asked vs publisher-asked; some-items-empty
  vs this-friend-item-empty.

  Lock: CONFOUNDED stands; real-feed-001 is not promoted to real;
  self_reported is retained. The overgeneralization itself is a new
  must-red sample. "Some siblings have an empty preview" is not
  evidence about the friend item.

Arms (must-fail + control, paired):
  1. OVERGENERALIZE_MUST_RED — friend preview non-empty, a sibling
     preview empty, observer claims friend preview empty via
     sibling generalization → FAIL OVERGENERALIZE
  2. OVERGENERALIZE_HONEST — same facts, recorded OVERGENERALIZE,
     not claimed as established → PASS OVERGENERALIZE
  3. DISTINGUISHED_PASS — same split facts, observer reads the
     friend item and reports non-empty → PASS DISTINGUISHED
  4. VACUOUS_TRUE_MUST_RED — friend preview is empty, but the
     observer inferred that from siblings rather than reading the
     friend item (right conclusion, wrong method) → FAIL OVERGENERALIZE
  5. DIRECT_EMPTY_PASS — friend preview empty, observed on the
     friend item itself → PASS EMPTY
  6. NO_FRIEND_MUST_RED — no friend item in the array, observer
     claims friend preview empty → FAIL UNKNOWN
  7. NO_FRIEND_HONEST — no friend item, recorded UNKNOWN → PASS UNKNOWN
  8. COLLAPSED_AS_DATA_GAP — friend preview non-empty, observer
     claims empty and records it as NEEDS_FEED_GET (a data gap)
     rather than an observer error → FAIL OVERGENERALIZE

analyze_only. Stdlib only.
Credit: 光盘dvd (self-correction + overgeneralization sample +
        sibling-empty vs friend-empty split);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import json
import sys
from typing import Any


def _preview_empty(item: dict[str, Any] | None) -> bool:
    if item is None:
        return True
    text = item.get("preview_text")
    return text is None or text == ""


def _find_friend(items: list[dict[str, Any]], friend_item_id: Any) -> dict[str, Any] | None:
    if friend_item_id is not None:
        for item in items:
            if item.get("item_id") == friend_item_id:
                return item
    for item in items:
        if item.get("author_relation") == "friend":
            return item
    return None


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    items = list(receipt.get("items") or [])
    friend_id = receipt.get("friend_item_id")
    claim = receipt.get("observer_claim")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state")
    observed_via = receipt.get("observed_via") or "unspecified"

    friend = _find_friend(items, friend_id)
    siblings = [item for item in items if item is not friend]
    sibling_empty = any(_preview_empty(item) for item in siblings)
    via_sibling = observed_via == "sibling_generalization"

    if friend is None:
        detail = {
            "friend_item_id": friend_id,
            "n_items": len(items),
            "sibling_empty": sibling_empty,
            "note": "no friend item in the observed array",
        }
        if recorded == "UNKNOWN" and not claimed_ok and claim in (None, "unknown"):
            return {
                "judge": "PASS",
                "reason_code": "UNKNOWN",
                "detail": {**detail, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "UNKNOWN",
            "detail": {**detail, "observer_claim": claim, "claimed_ok": claimed_ok},
        }

    friend_empty = _preview_empty(friend)
    detail = {
        "friend_item_id": friend.get("item_id"),
        "friend_preview_empty": friend_empty,
        "friend_preview_len": 0 if friend_empty else len(str(friend.get("preview_text"))),
        "sibling_empty": sibling_empty,
        "observed_via": observed_via,
        "observer_claim": claim,
    }

    # Method error: concluding from siblings, not from the friend item.
    if via_sibling or (claim == "friend_preview_empty" and not friend_empty):
        if recorded == "OVERGENERALIZE" and not claimed_ok:
            return {
                "judge": "PASS",
                "reason_code": "OVERGENERALIZE",
                "detail": {**detail, "honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "OVERGENERALIZE",
            "detail": {
                **detail,
                "claimed_ok": claimed_ok,
                "recorded_state": recorded,
                "note": (
                    "sibling empty preview is not evidence about the friend item"
                    if not friend_empty
                    else "empty friend preview must be read on the friend item, not inferred from siblings"
                ),
            },
        }

    if friend_empty:
        if claim == "friend_preview_empty" and observed_via == "friend_item":
            return {
                "judge": "PASS",
                "reason_code": "EMPTY",
                "detail": {**detail, "direct": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "EMPTY",
            "detail": {**detail, "note": "friend preview is empty on direct read"},
        }

    if claim == "friend_preview_nonempty" and observed_via == "friend_item":
        return {
            "judge": "PASS",
            "reason_code": "DISTINGUISHED",
            "detail": {**detail, "direct": True},
        }

    if claim == "friend_preview_nonempty":
        return {
            "judge": "PASS",
            "reason_code": "DISTINGUISHED",
            "detail": detail,
        }

    return {
        "judge": "FAIL",
        "reason_code": "OVERGENERALIZE",
        "detail": {**detail, "claimed_ok": claimed_ok},
    }


FRIEND_NONEMPTY = {
    "item_id": "375057318271778816",
    "author_relation": "friend",
    "preview_text": (
        "The author introduces a reliability principle distinguishing "
        "request accepted from action effective, with a 480-character "
        "class English abstract used as a non-empty friend preview."
    ),
    "preview_truncated": False,
}

SIBLING_EMPTY = {
    "item_id": "stranger-empty-001",
    "author_relation": "stranger",
    "preview_text": "",
    "preview_truncated": False,
}

FRIEND_EMPTY = {
    "item_id": "friend-empty-001",
    "author_relation": "friend",
    "preview_text": "",
    "preview_truncated": False,
}

COMMON_META = {
    "evidence_ref": "fixture://derived/observer-overgeneralizes-empty-preview#v1",
    "coverage": "n=1 batch x 1 assertion",
    "fixture_version": "v1",
}


FIXTURES = [
    {
        "case_id": "OOEP-OVERGENERALIZE-MUST-RED",
        "receipt": {
            "kind": "overgeneralize_must_red",
            "fixture_id": "observer.empty.preview.overgen.v1",
            "friend_item_id": FRIEND_NONEMPTY["item_id"],
            "items": [FRIEND_NONEMPTY, SIBLING_EMPTY],
            "observer_claim": "friend_preview_empty",
            "observed_via": "sibling_generalization",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "OVERGENERALIZE",
    },
    {
        "case_id": "OOEP-OVERGENERALIZE-HONEST",
        "receipt": {
            "kind": "overgeneralize_honest",
            "fixture_id": "observer.empty.preview.overgen.honest.v1",
            "friend_item_id": FRIEND_NONEMPTY["item_id"],
            "items": [FRIEND_NONEMPTY, SIBLING_EMPTY],
            "observer_claim": "friend_preview_empty",
            "observed_via": "sibling_generalization",
            "claimed_ok": False,
            "recorded_state": "OVERGENERALIZE",
            **COMMON_META,
        },
        "expect": "OVERGENERALIZE",
    },
    {
        "case_id": "OOEP-DISTINGUISHED-PASS",
        "receipt": {
            "kind": "distinguished_pass",
            "fixture_id": "observer.empty.preview.distinguished.v1",
            "friend_item_id": FRIEND_NONEMPTY["item_id"],
            "items": [FRIEND_NONEMPTY, SIBLING_EMPTY],
            "observer_claim": "friend_preview_nonempty",
            "observed_via": "friend_item",
            "claimed_ok": True,
            "must_not_trip": ["OVERGENERALIZE", "UNKNOWN", "EMPTY"],
            **COMMON_META,
        },
        "expect": "DISTINGUISHED",
    },
    {
        "case_id": "OOEP-VACUOUS-TRUE-MUST-RED",
        "receipt": {
            "kind": "vacuous_true_must_red",
            "fixture_id": "observer.empty.preview.vacuous.v1",
            "friend_item_id": FRIEND_EMPTY["item_id"],
            "items": [FRIEND_EMPTY, SIBLING_EMPTY],
            "observer_claim": "friend_preview_empty",
            "observed_via": "sibling_generalization",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "OVERGENERALIZE",
    },
    {
        "case_id": "OOEP-DIRECT-EMPTY-PASS",
        "receipt": {
            "kind": "direct_empty_pass",
            "fixture_id": "observer.empty.preview.direct.empty.v1",
            "friend_item_id": FRIEND_EMPTY["item_id"],
            "items": [FRIEND_EMPTY, SIBLING_EMPTY],
            "observer_claim": "friend_preview_empty",
            "observed_via": "friend_item",
            "claimed_ok": True,
            "must_not_trip": ["OVERGENERALIZE"],
            **COMMON_META,
        },
        "expect": "EMPTY",
    },
    {
        "case_id": "OOEP-NO-FRIEND-MUST-RED",
        "receipt": {
            "kind": "no_friend_must_red",
            "fixture_id": "observer.empty.preview.no.friend.v1",
            "friend_item_id": "375057318271778816",
            "items": [SIBLING_EMPTY],
            "observer_claim": "friend_preview_empty",
            "observed_via": "sibling_generalization",
            "claimed_ok": True,
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "OOEP-NO-FRIEND-HONEST",
        "receipt": {
            "kind": "no_friend_honest",
            "fixture_id": "observer.empty.preview.no.friend.honest.v1",
            "friend_item_id": "375057318271778816",
            "items": [SIBLING_EMPTY],
            "observer_claim": "unknown",
            "observed_via": "unspecified",
            "claimed_ok": False,
            "recorded_state": "UNKNOWN",
            **COMMON_META,
        },
        "expect": "UNKNOWN",
    },
    {
        "case_id": "OOEP-COLLAPSED-AS-DATA-GAP",
        "receipt": {
            "kind": "collapsed_as_data_gap",
            "fixture_id": "observer.empty.preview.collapsed.v1",
            "friend_item_id": FRIEND_NONEMPTY["item_id"],
            "items": [FRIEND_NONEMPTY, SIBLING_EMPTY],
            "observer_claim": "friend_preview_empty",
            "observed_via": "sibling_generalization",
            "claimed_ok": True,
            "recorded_state": "NEEDS_FEED_GET",
            **COMMON_META,
        },
        "expect": "OVERGENERALIZE",
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
        "version": "OBSERVER_OVERGENERALIZES_EMPTY_PREVIEW/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "光盘dvd (self-correction + overgeneralization sample + sibling-empty vs friend-empty split)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
