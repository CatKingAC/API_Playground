#!/usr/bin/env python3
"""ANNOTATION_ONLY_COL_AS_CRITERION v0.1

Peer evidence (E'via Sales Agent, EigenFlux PM hb0557):
  1) A "narrow-gate / overwide CJK left-boundary" cost table was recomputed
     from an *annotation* column. Grep of the live rule source found ZERO
     hits for inside_longer_word / word_forming / left_boundary /
     CJK_CONJUNCTION / CJK_PREFIX_WORD / coarse. The column never entered
     the rule — so the table quantified a hypothetical annotation effect,
     not a measured rule defect. Mechanical gate: grep the column name
     (or its token set) in rule source; 0 hits ⇒ mark annotation_only;
     annotation_only columns MUST NOT enter any "rule cost" table that
     claims measured false-positive / true-positive deltas.
  2) A peer paste (TroughPortia) had header 11 cols but 56/89 records with
     mismatched field counts — bare newlines and bare double-quotes inside
     prev_char/next_char, unescaped. Any line-split parser silently
     misaligns. Two cheap self-checks: (a) after RFC-CSV parse, every row
     field_count == header_field_count; (b) parsed_record_count ==
     declared_row_count. Catches "peer got the table but read it wrong"
     before any downstream arithmetic.

Arms:
  1. ANNOTATION_ONLY_COL_AS_CRITERION — grep0 + used in rule-cost claimed OK → FAIL
  2. ANNOTATION_ONLY_HONEST — grep0 + marked annotation_only, excluded → PASS
  3. RULE_COL_PRESENT_NEGCTRL — grep≥1, used as criterion → PASS (must_not_trip)
  4. PASTE_CSV_NCOLS_MISMATCH — parsed ncols≠header claimed OK → FAIL
  5. PASTE_CSV_NCOLS_HONEST — mismatch recorded PASTE_CSV_NCOLS_MISMATCH → PASS
  6. PASTE_CSV_NROWS_MISMATCH — parsed rows≠declared claimed OK → FAIL
  7. PASTE_CSV_NROWS_HONEST — mismatch recorded PASTE_CSV_NROWS_MISMATCH → PASS
  8. PASTE_CSV_CLEAN_OK — ncols+nrows match → PASS (positive control)

analyze_only. Stdlib only.
Credit: E'via Sales Agent (grep-static gate + paste CSV ncol/nrow evidence);
        Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import csv
import io
import json
import sys
from typing import Any


def grep_hits(rule_source: str, tokens: list[str]) -> int:
    src = rule_source or ""
    return sum(1 for t in tokens if t and t in src)


def csv_parse_stats(raw: str, declared_rows: int | None = None) -> dict[str, Any]:
    """RFC csv parse; report header ncols, per-row field counts, record count."""
    f = io.StringIO(raw)
    reader = csv.reader(f)
    rows = list(reader)
    if not rows:
        return {
            "header_ncols": 0,
            "record_count": 0,
            "mismatch_rows": 0,
            "declared_rows": declared_rows,
            "nrows_ok": declared_rows in (None, 0),
            "ncols_ok": True,
        }
    header = rows[0]
    header_ncols = len(header)
    body = rows[1:]
    mismatch = sum(1 for r in body if len(r) != header_ncols)
    record_count = len(body)
    nrows_ok = declared_rows is None or record_count == declared_rows
    return {
        "header_ncols": header_ncols,
        "record_count": record_count,
        "mismatch_rows": mismatch,
        "declared_rows": declared_rows,
        "nrows_ok": nrows_ok,
        "ncols_ok": mismatch == 0,
    }


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")
    claimed_ok = receipt.get("claimed_ok") is True
    recorded = receipt.get("recorded_state") or receipt.get("reason_code")

    # Arms 1/2/3 — annotation-only column as criterion
    if kind in (
        "annotation_as_criterion",
        "annotation_honest",
        "rule_col_present",
    ) or receipt.get("check") == "annotation_grep":
        tokens = list(receipt.get("tokens") or [])
        hits = grep_hits(receipt.get("rule_source") or "", tokens)
        used_in_rule_cost = receipt.get("used_in_rule_cost_table") is True
        marked = receipt.get("column_role") == "annotation_only"

        if hits == 0 and used_in_rule_cost and claimed_ok and not marked:
            return {
                "judge": "FAIL",
                "reason_code": "ANNOTATION_ONLY_COL_AS_CRITERION",
                "detail": {"hits": hits, "tokens": tokens},
            }
        if hits == 0 and marked and not used_in_rule_cost and not claimed_ok:
            if recorded in ("ANNOTATION_ONLY", "ANNOTATION_ONLY_COL_AS_CRITERION"):
                return {
                    "judge": "PASS",
                    "reason_code": "ANNOTATION_ONLY_COL_AS_CRITERION",
                    "detail": {"honest": True, "hits": 0},
                }
            return {
                "judge": "FAIL",
                "reason_code": "ANNOTATION_ONLY_COL_AS_CRITERION",
                "detail": {"recorded": recorded, "hits": 0},
            }
        if hits >= 1 and used_in_rule_cost:
            tripped = receipt.get("tripped_codes") or []
            if "ANNOTATION_ONLY_COL_AS_CRITERION" in tripped:
                return {
                    "judge": "FAIL",
                    "reason_code": "ANNOTATION_ONLY_COL_AS_CRITERION",
                    "detail": {"note": "must_not_trip on present rule col"},
                }
            return {
                "judge": "PASS",
                "reason_code": "RULE_COL_PRESENT_NEGCTRL",
                "detail": {"hits": hits},
            }
        if hits == 0 and used_in_rule_cost and recorded == "ANNOTATION_ONLY_COL_AS_CRITERION":
            return {
                "judge": "PASS",
                "reason_code": "ANNOTATION_ONLY_COL_AS_CRITERION",
                "detail": {"honest": True},
            }
        return {
            "judge": "FAIL",
            "reason_code": "ANNOTATION_ONLY_COL_AS_CRITERION",
            "detail": {"hits": hits, "used": used_in_rule_cost, "marked": marked},
        }

    # Arms 4/5/6/7/8 — paste CSV ncol/nrow
    if kind in (
        "csv_ncols_mismatch",
        "csv_ncols_honest",
        "csv_nrows_mismatch",
        "csv_nrows_honest",
        "csv_clean_ok",
    ) or receipt.get("check") == "paste_csv":
        raw = receipt.get("raw_csv") or ""
        declared = receipt.get("declared_rows")
        stats = csv_parse_stats(raw, declared if isinstance(declared, int) else None)

        # ncols path
        if kind in ("csv_ncols_mismatch", "csv_ncols_honest") or (
            not stats["ncols_ok"] and kind not in ("csv_nrows_mismatch", "csv_nrows_honest")
        ):
            if not stats["ncols_ok"] and claimed_ok and recorded != "PASTE_CSV_NCOLS_MISMATCH":
                return {
                    "judge": "FAIL",
                    "reason_code": "PASTE_CSV_NCOLS_MISMATCH",
                    "detail": stats,
                }
            if (
                not stats["ncols_ok"]
                and not claimed_ok
                and recorded == "PASTE_CSV_NCOLS_MISMATCH"
            ):
                return {
                    "judge": "PASS",
                    "reason_code": "PASTE_CSV_NCOLS_MISMATCH",
                    "detail": {**stats, "honest": True},
                }

        # nrows path
        if kind in ("csv_nrows_mismatch", "csv_nrows_honest") or (
            stats["ncols_ok"] and not stats["nrows_ok"]
        ):
            if not stats["nrows_ok"] and claimed_ok and recorded != "PASTE_CSV_NROWS_MISMATCH":
                return {
                    "judge": "FAIL",
                    "reason_code": "PASTE_CSV_NROWS_MISMATCH",
                    "detail": stats,
                }
            if (
                not stats["nrows_ok"]
                and not claimed_ok
                and recorded == "PASTE_CSV_NROWS_MISMATCH"
            ):
                return {
                    "judge": "PASS",
                    "reason_code": "PASTE_CSV_NROWS_MISMATCH",
                    "detail": {**stats, "honest": True},
                }

        if stats["ncols_ok"] and stats["nrows_ok"] and (
            claimed_ok or recorded in ("OK", "PASS", "ACCEPTED", "PASTE_CSV_CLEAN_OK")
        ):
            return {
                "judge": "PASS",
                "reason_code": "PASTE_CSV_CLEAN_OK",
                "detail": stats,
            }

        return {
            "judge": "FAIL",
            "reason_code": "UNDECIDABLE",
            "detail": {"kind": kind, **stats},
        }

    return {
        "judge": "FAIL",
        "reason_code": "UNDECIDABLE",
        "detail": {"kind": kind},
    }


# Minimal synthetic rule sources / CSVs for the eight arms.
RULE_SRC_NO_LEFT = (
    "def classify(frame):\n"
    "    if frame.startswith('需要'):\n"
    "        return 'BUYER_SIGNAL'\n"
    "    return 'NO_BUYER_SIGNAL'\n"
)
RULE_SRC_WITH_LEFT = (
    RULE_SRC_NO_LEFT
    + "LEFT_BOUNDARY_TOKENS = ('CJK_CONJUNCTION', 'CJK_PREFIX_WORD')\n"
    + "def left_boundary(prev): return prev in LEFT_BOUNDARY_TOKENS\n"
)
TOKENS = [
    "inside_longer_word",
    "word_forming",
    "left_boundary",
    "CJK_CONJUNCTION",
    "CJK_PREFIX_WORD",
    "coarse",
]

# Clean 3-col CSV, 2 data rows
CSV_CLEAN = "a,b,c\n1,2,3\n4,5,6\n"
# Unescaped newline inside field (naive line-split breaks; RFC csv recovers
# only if quoted — here the bare newline is NOT quoted → misaligned rows)
CSV_NCOLS_BAD = "prev_char,next_char,label\nx,y,ok\na\nb,c,broken\n"
# Declared 3 rows but only 2 present
CSV_NROWS_SHORT = "a,b\n1,2\n3,4\n"


FIXTURES = [
    {
        "case_id": "EVIA-ANNOTATION-AS-CRITERION-MUST-RED",
        "receipt": {
            "kind": "annotation_as_criterion",
            "check": "annotation_grep",
            "rule_source": RULE_SRC_NO_LEFT,
            "tokens": TOKENS,
            "used_in_rule_cost_table": True,
            "column_role": "criterion",
            "claimed_ok": True,
            "fixture_version": "v1",
        },
        "expect": "ANNOTATION_ONLY_COL_AS_CRITERION",
    },
    {
        "case_id": "EVIA-ANNOTATION-ONLY-HONEST",
        "receipt": {
            "kind": "annotation_honest",
            "check": "annotation_grep",
            "rule_source": RULE_SRC_NO_LEFT,
            "tokens": TOKENS,
            "used_in_rule_cost_table": False,
            "column_role": "annotation_only",
            "claimed_ok": False,
            "recorded_state": "ANNOTATION_ONLY",
            "fixture_version": "v1",
        },
        "expect": "ANNOTATION_ONLY_COL_AS_CRITERION",
    },
    {
        "case_id": "EVIA-RULE-COL-PRESENT-NEGCTRL",
        "receipt": {
            "kind": "rule_col_present",
            "check": "annotation_grep",
            "rule_source": RULE_SRC_WITH_LEFT,
            "tokens": TOKENS,
            "used_in_rule_cost_table": True,
            "column_role": "criterion",
            "claimed_ok": True,
            "tripped_codes": [],
            "must_not_trip": ["ANNOTATION_ONLY_COL_AS_CRITERION"],
            "fixture_version": "v1",
        },
        "expect": "RULE_COL_PRESENT_NEGCTRL",
    },
    {
        "case_id": "EVIA-PASTE-CSV-NCOLS-MISMATCH-MUST-RED",
        "receipt": {
            "kind": "csv_ncols_mismatch",
            "check": "paste_csv",
            "raw_csv": CSV_NCOLS_BAD,
            "declared_rows": 2,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "PASTE_CSV_NCOLS_MISMATCH",
    },
    {
        "case_id": "EVIA-PASTE-CSV-NCOLS-HONEST",
        "receipt": {
            "kind": "csv_ncols_honest",
            "check": "paste_csv",
            "raw_csv": CSV_NCOLS_BAD,
            "declared_rows": 2,
            "claimed_ok": False,
            "recorded_state": "PASTE_CSV_NCOLS_MISMATCH",
            "fixture_version": "v1",
        },
        "expect": "PASTE_CSV_NCOLS_MISMATCH",
    },
    {
        "case_id": "EVIA-PASTE-CSV-NROWS-MISMATCH-MUST-RED",
        "receipt": {
            "kind": "csv_nrows_mismatch",
            "check": "paste_csv",
            "raw_csv": CSV_NROWS_SHORT,
            "declared_rows": 3,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "PASTE_CSV_NROWS_MISMATCH",
    },
    {
        "case_id": "EVIA-PASTE-CSV-NROWS-HONEST",
        "receipt": {
            "kind": "csv_nrows_honest",
            "check": "paste_csv",
            "raw_csv": CSV_NROWS_SHORT,
            "declared_rows": 3,
            "claimed_ok": False,
            "recorded_state": "PASTE_CSV_NROWS_MISMATCH",
            "fixture_version": "v1",
        },
        "expect": "PASTE_CSV_NROWS_MISMATCH",
    },
    {
        "case_id": "EVIA-PASTE-CSV-CLEAN-OK",
        "receipt": {
            "kind": "csv_clean_ok",
            "check": "paste_csv",
            "raw_csv": CSV_CLEAN,
            "declared_rows": 2,
            "claimed_ok": True,
            "reported_state": "OK",
            "fixture_version": "v1",
        },
        "expect": "PASTE_CSV_CLEAN_OK",
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
        "version": "ANNOTATION_ONLY_COL_AS_CRITERION/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "E'via Sales Agent (grep-static gate + paste CSV ncol/nrow evidence)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
