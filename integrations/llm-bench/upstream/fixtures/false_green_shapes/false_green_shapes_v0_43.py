#!/usr/bin/env python3
"""FALSE_GREEN_SHAPES v0.43

Adds two peer-supplied shapes on top of v0.42 (prior files untouched; S7-S76
rows re-run here by import so one command checks S7-S78).

  S77 MISSING_AS_ZERO / NULL_COLLAPSED_TO_ZERO
      Empty-set / missing aggregate must stay null (or explicit missing), not
      silently become 0.0. Distinct from S23 VACUOUS_EMPTY_AGGREGATE (health
      metrics age/errors with n==0 looking "cleared"): this shape is about the
      semantic of missing vs measured-zero on a numeric aggregate field.
      Rules while claiming sum_ok / aggregate_ok / value_ok:
        - empty_set True (or cardinality==0) AND expected is None AND
          actual is 0 or 0.0 → FAIL/MISSING_AS_ZERO
        - empty_set True AND actual is None (missing preserved) → OK
        - cardinality>0 with actual measured → OK
        - claiming without empty_set/cardinality/expected/actual →
          UNKNOWN/EMPTY_SET_UNDECLARED
      Naive greens: actual==0 / actual==0.0 / sum==0 / ok True.
      Credit: 郑珺的hermes (EigenFlux — FGS-HB1602 three-col synthetic;
      expected=null / actual=0.0 / FAIL(MISSING_AS_ZERO)).

  S78 FLOAT_ID_ULP_COLLAPSE / ASSERT_EQUAL_AFTER_FLOAT64
      Assertion-layer id equality that routes expected through float64 loses
      ULP and greens a collapsed actual. Distinct from S18 (transport/safe-
      integer boundary on number ids) and S72 (lookup/parse path precision
      loss): this shape fires when an assertion claims id_match_ok while
      expected != actual and actual == int(float(expected)).
      Rules while claiming id_match_ok / assert_ok / equal_ok:
        - expected and actual both present; if str(expected)!=str(actual) and
          int(float(int(expected))) == int(actual) → FAIL/FLOAT_ID_ULP_COLLAPSE
        - expected == actual (string-exact) → OK
        - claiming without expected or actual → UNKNOWN/ID_ASSERT_UNDECLARED
      Naive greens: abs(float(expected)-float(actual))<1 / float-equal / ok True.
      Credit: 郑珺的hermes (EigenFlux — expected=9007199254740993 /
      actual=9007199254740992 / FAIL(FLOAT_ID_ULP_COLLAPSE); criteria fgs.v1).

analyze_only. Stdlib only. Run: python3 false_green_shapes_v0_43.py
"""
from __future__ import annotations
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import false_green_shapes_v0_42 as v42


def s77_naive(r):
    if r.get("sum_ok") is True or r.get("aggregate_ok") is True or r.get("value_ok") is True:
        return "OK"
    if r.get("ok") is True or r.get("status") == "ok":
        return "OK"
    actual = r.get("actual", r.get("sum"))
    if actual == 0 or actual == 0.0:
        return "OK"
    return "FAIL"


def s77_struct(r):
    claiming = (
        r.get("sum_ok") is True
        or r.get("aggregate_ok") is True
        or r.get("value_ok") is True
        or r.get("claiming_value_ok") is True
        or r.get("ok") is True
        or r.get("status") == "ok"
    )
    if not claiming:
        return "FAIL"
    empty = r.get("empty_set")
    card = r.get("cardinality")
    if empty is None and card is None:
        return "UNKNOWN/EMPTY_SET_UNDECLARED"
    is_empty = empty is True or card == 0
    expected = r.get("expected")
    actual = r.get("actual")
    if actual is None and "sum" in r:
        actual = r.get("sum")
    if expected is None and "expected" not in r and "expected_sum" in r:
        expected = r.get("expected_sum")
    if is_empty:
        if expected is None and (actual == 0 or actual == 0.0):
            return "FAIL/MISSING_AS_ZERO"
        if actual is None:
            return "OK"
        if expected is None and actual is not None and actual != 0 and actual != 0.0:
            return "FAIL/MISSING_AS_ZERO"
    if expected is None or actual is None:
        if "expected" not in r and "actual" not in r and "sum" not in r:
            return "UNKNOWN/EMPTY_SET_UNDECLARED"
    return "OK"


def _to_int(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str) and v.lstrip("-").isdigit():
        return int(v)
    return None


def s78_naive(r):
    if r.get("id_match_ok") is True or r.get("assert_ok") is True or r.get("equal_ok") is True:
        return "OK"
    if r.get("ok") is True or r.get("status") == "ok":
        return "OK"
    exp = r.get("expected")
    act = r.get("actual")
    if exp is not None and act is not None:
        try:
            if abs(float(exp) - float(act)) < 1.0:
                return "OK"
        except (TypeError, ValueError):
            pass
    return "FAIL"


def s78_struct(r):
    claiming = (
        r.get("id_match_ok") is True
        or r.get("assert_ok") is True
        or r.get("equal_ok") is True
        or r.get("claiming_id_match") is True
        or r.get("ok") is True
        or r.get("status") == "ok"
    )
    if not claiming:
        return "FAIL"
    exp = r.get("expected")
    act = r.get("actual")
    if exp is None or act is None:
        return "UNKNOWN/ID_ASSERT_UNDECLARED"
    if str(exp) == str(act):
        return "OK"
    ei = _to_int(exp)
    ai = _to_int(act)
    if ei is None or ai is None:
        return "FAIL/FLOAT_ID_ULP_COLLAPSE"
    collapsed = int(float(ei))
    if collapsed != ei and ai == collapsed:
        return "FAIL/FLOAT_ID_ULP_COLLAPSE"
    if ei != ai:
        # still a mismatch under claim
        return "FAIL/FLOAT_ID_ULP_COLLAPSE"
    return "OK"


NEW_ROWS = [
  ("S77-mf-null-to-zero", "S77", "observed_shape_desensitized(郑珺的hermes)",
   {"empty_set": True, "cardinality": 0, "expected": None, "actual": 0.0,
    "sum_ok": True, "status": "ok", "criteria_version": "fgs.v1", "synthetic": True},
   "FAIL/MISSING_AS_ZERO", True),
  ("S77-mf-sum-zero-on-empty", "S77", "hand_built",
   {"empty_set": True, "expected": None, "sum": 0.0, "aggregate_ok": True, "ok": True},
   "FAIL/MISSING_AS_ZERO", True),
  ("S77-ct-undeclared-empty", "S77", "hand_built",
   {"actual": 0.0, "sum_ok": True, "status": "ok"},
   "UNKNOWN/EMPTY_SET_UNDECLARED", True),
  ("S77-gt-null-preserved", "S77", "observed_shape_desensitized(郑珺的hermes)",
   {"empty_set": True, "cardinality": 0, "expected": None, "actual": None,
    "value_ok": True, "status": "ok", "criteria_version": "fgs.v1"},
   "OK", False),
  ("S77-gt-measured-zero", "S77", "hand_built",
   {"empty_set": False, "cardinality": 12, "expected": 0.0, "actual": 0.0,
    "sum_ok": True, "ok": True},
   "OK", False),
  ("S78-mf-59bit-ulp", "S78", "observed_shape_desensitized(郑珺的hermes)",
   {"expected": 9007199254740993, "actual": 9007199254740992,
    "id_match_ok": True, "status": "ok", "criteria_version": "fgs.v1", "synthetic": True},
   "FAIL/FLOAT_ID_ULP_COLLAPSE", True),
  ("S78-mf-float-equal-green", "S78", "hand_built",
   {"expected": "9007199254740993", "actual": "9007199254740992",
    "assert_ok": True, "ok": True},
   "FAIL/FLOAT_ID_ULP_COLLAPSE", True),
  ("S78-ct-undeclared", "S78", "hand_built",
   {"id_match_ok": True, "status": "ok"},
   "UNKNOWN/ID_ASSERT_UNDECLARED", True),
  ("S78-gt-string-exact", "S78", "observed_shape_desensitized(郑珺的hermes)",
   {"expected": "9007199254740993", "actual": "9007199254740993",
    "id_match_ok": True, "equal_ok": True, "status": "ok"},
   "OK", False),
]

FNS = dict(v42.FNS)
FNS.update({
    "S77": (s77_naive, s77_struct),
    "S78": (s78_naive, s78_struct),
})
ROWS = list(v42.ROWS) + NEW_ROWS
CANT_TELL = ("UNKNOWN", "UNDECIDABLE", "RETRYABLE")

def main():
    ok = 0; out = []; naive_wrong = 0
    for rid, shape, prov, arg, exp, mf in ROWS:
        naive, struct = FNS[shape]
        g, n = struct(arg), naive(arg)
        passed = (g == exp) and ((n != exp) if mf else (n == exp))
        naive_wrong += (n != exp)
        ok += passed
        out.append({"id": rid, "shape": shape, "provenance": prov, "expected": exp,
                    "struct": g, "naive": n, "must_fail_arm": mf, "pass": passed})
    ct = [r for r in out if r["expected"].split("/")[0] in CANT_TELL]
    forced = sum(1 for r in ct if r["naive"] in ("OK", "FAIL"))
    ctl = forced == len(ct)
    ok += ctl
    total = len(ROWS) + 1
    new_wrong = sum(1 for r in out if r["shape"] in ("S77", "S78") and r["naive"] != r["expected"])
    res = {"fixture": "FALSE_GREEN_SHAPES", "version": "0.43", "selftest": f"{ok}/{total}",
           "naive_wrong_rows": naive_wrong, "naive_wrong_new_shapes": f"{new_wrong}/{len(NEW_ROWS)}",
           "naive_forced_verdicts_on_cant_tell": forced, "forced_verdict_control": ctl, "rows": out}
    json.dump(res, open("run_out_v0_43.json", "w"), ensure_ascii=False, indent=1)
    print(f"selftest {ok}/{total}; naive wrong {naive_wrong}/{len(ROWS)} (new shapes {new_wrong}/{len(NEW_ROWS)}); forced verdicts on can't-tell {forced}/{len(ct)}")
    for r in out:
        if not r["pass"]:
            print("FAIL_ROW", r)
    return 0 if ok == total else 1

if __name__ == "__main__":
    raise SystemExit(main())
