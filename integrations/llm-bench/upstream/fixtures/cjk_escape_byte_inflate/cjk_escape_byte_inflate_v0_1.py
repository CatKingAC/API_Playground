#!/usr/bin/env python3
"""CJK_ESCAPE_BYTE_INFLATE v0.1

Peer evidence (DeepSeek-Harness field-lock, EigenFlux PM hb0434/hb0502):
  Dual-layer receipt: receipt_exec (declared_*) vs receipt_delivery
  (receiver_computed_*); issuers must differ. Three negctrl shapes:
    ① 变长双向 — CJK / \\uXXXX escape inflates UTF-8 byte length while
       char-count or declared_len stays equal → false-green ACCEPTED.
    ② 等长换字 — equal byte length, different digest (substitution)
       → must surface EQUAL_LEN_DIFF_DIGEST / CORRUPTED, not PASS.
    ③ 回执自截断 — half-truncated receipt still claimed delivered →
       must be UNKNOWN (RECEIPT_HALF_TRUNC_UNKNOWN), never ACCEPTED.

Arms:
  1. CJK_ESCAPE_BYTE_INFLATE — escape form byte_len > raw UTF-8 byte_len
     while claimed_ok / ACCEPTED → FAIL
  2. CJK_ESCAPE_HONEST — same inflate recorded as TRUNCATED|CORRUPTED
     with receiver_computed_* mismatch → PASS (honest)
  3. EQUAL_LEN_DIFF_DIGEST — size_equal True, digest unequal, claimed
     ACCEPTED → FAIL
  4. EQUAL_LEN_DIFF_HONEST — size_equal, digest unequal, recorded
     CORRUPTED → PASS
  5. RECEIPT_HALF_TRUNC_UNKNOWN — receipt bytes truncated mid-field,
     claimed ACCEPTED/delivered → FAIL (must be UNKNOWN)
  6. RECEIPT_HALF_TRUNC_HONEST — truncated + recorded UNKNOWN with
     reason_code RECEIPT_HALF_TRUNC_UNKNOWN → PASS
  7. DECLARED_EQ_RECV_OK — declared_* == receiver_computed_* both sides
     independent → PASS (positive control)
  8. SAME_ISSUER_NOT_INDEPENDENT — receipt_exec issuer == receipt_delivery
     issuer while claimed independent → FAIL (NOT_INDEPENDENT)

analyze_only. Stdlib only.
Credit: DeepSeek-Harness (field-lock FOUR_STATE + dual receipt + three
        negctrl shapes); Grok Bot (impl + must-fail samples).
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _as_bytes(v: Any) -> bytes | None:
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    if isinstance(v, str):
        return v.encode("utf-8")
    return None


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    kind = receipt.get("kind")

    # Arm 8 — same issuer
    if kind in ("same_issuer", "indep_ok") or receipt.get("issuer_exec") is not None:
        ie = receipt.get("issuer_exec")
        idel = receipt.get("issuer_delivery")
        claimed_indep = receipt.get("claimed_independent") is True
        if ie is not None and idel is not None and ie == idel and claimed_indep:
            return {
                "judge": "FAIL",
                "reason_code": "NOT_INDEPENDENT",
                "detail": {"issuer": ie},
            }
        if (
            kind == "indep_ok"
            and ie is not None
            and idel is not None
            and ie != idel
            and claimed_indep
        ):
            # fall through to positive control checks below if present
            pass

    # Arm 5/6 — half-trunc receipt
    if kind in ("half_trunc_false_ok", "half_trunc_honest") or receipt.get(
        "receipt_truncated"
    ) is True:
        truncated = receipt.get("receipt_truncated") is True
        claimed = receipt.get("claimed_ok") is True or receipt.get(
            "reported_state"
        ) in ("ACCEPTED", "DELIVERED", "OK", "PASS")
        recorded = receipt.get("recorded_state")
        reason = receipt.get("reason_code")
        if truncated and claimed and recorded != "UNKNOWN":
            return {
                "judge": "FAIL",
                "reason_code": "RECEIPT_HALF_TRUNC_UNKNOWN",
                "detail": {
                    "receipt_truncated": True,
                    "note": "half-trunc must be UNKNOWN not ACCEPTED",
                },
            }
        if (
            truncated
            and recorded == "UNKNOWN"
            and reason == "RECEIPT_HALF_TRUNC_UNKNOWN"
        ):
            return {
                "judge": "PASS",
                "reason_code": "RECEIPT_HALF_TRUNC_UNKNOWN",
                "detail": {"honest": True},
            }

    # Arm 3/4 — equal length different digest
    if kind in ("equal_len_diff", "equal_len_honest") or (
        receipt.get("size_equal") is True and receipt.get("digest_equal") is False
    ):
        size_eq = receipt.get("size_equal")
        dig_eq = receipt.get("digest_equal")
        # recompute if raw present
        raw_a = _as_bytes(receipt.get("raw_a"))
        raw_b = _as_bytes(receipt.get("raw_b"))
        if raw_a is not None and raw_b is not None:
            size_eq = len(raw_a) == len(raw_b)
            dig_eq = _sha(raw_a) == _sha(raw_b)
        claimed = receipt.get("claimed_ok") is True or receipt.get(
            "reported_state"
        ) in ("ACCEPTED", "OK", "PASS")
        recorded = receipt.get("recorded_state")
        if size_eq is True and dig_eq is False and claimed:
            return {
                "judge": "FAIL",
                "reason_code": "EQUAL_LEN_DIFF_DIGEST",
                "detail": {"size_equal": True, "digest_equal": False},
            }
        if (
            size_eq is True
            and dig_eq is False
            and recorded in ("CORRUPTED", "EQUAL_LEN_DIFF_DIGEST")
        ):
            return {
                "judge": "PASS",
                "reason_code": "EQUAL_LEN_DIFF_DIGEST",
                "detail": {"honest": True},
            }

    # Arm 1/2 — CJK escape byte inflate
    if kind in ("cjk_inflate_false_ok", "cjk_inflate_honest") or receipt.get(
        "escape_form"
    ) is not None:
        raw = _as_bytes(receipt.get("raw_text"))
        esc = receipt.get("escape_form")
        esc_b = _as_bytes(esc) if esc is not None else None
        declared = receipt.get("payload_declared_bytes")
        recv = receipt.get("receiver_computed_bytes")
        claimed = receipt.get("claimed_ok") is True or receipt.get(
            "reported_state"
        ) in ("ACCEPTED", "OK", "PASS")
        recorded = receipt.get("recorded_state")

        inflate = False
        detail: dict[str, Any] = {}
        if raw is not None and esc_b is not None:
            inflate = len(esc_b) > len(raw)
            detail = {
                "raw_bytes": len(raw),
                "escape_bytes": len(esc_b),
                "char_count": len(receipt.get("raw_text") or ""),
            }
        elif (
            isinstance(declared, int)
            and isinstance(recv, int)
            and recv > declared
            and receipt.get("escape_applied") is True
        ):
            inflate = True
            detail = {"declared": declared, "receiver_computed": recv}

        if inflate and claimed and recorded not in ("TRUNCATED", "CORRUPTED"):
            return {
                "judge": "FAIL",
                "reason_code": "CJK_ESCAPE_BYTE_INFLATE",
                "detail": detail,
            }
        if inflate and recorded in ("TRUNCATED", "CORRUPTED", "CJK_ESCAPE_BYTE_INFLATE"):
            return {
                "judge": "PASS",
                "reason_code": "CJK_ESCAPE_BYTE_INFLATE",
                "detail": {**detail, "honest": True},
            }

    # Arm 7 — positive control declared == receiver
    if kind == "declared_eq_recv" or (
        receipt.get("payload_declared_bytes") is not None
        and receipt.get("receiver_computed_bytes") is not None
        and receipt.get("payload_declared_digest") is not None
        and receipt.get("receiver_computed_digest") is not None
    ):
        db = receipt.get("payload_declared_bytes")
        rb = receipt.get("receiver_computed_bytes")
        dd = receipt.get("payload_declared_digest")
        rd = receipt.get("receiver_computed_digest")
        ie = receipt.get("issuer_exec")
        idel = receipt.get("issuer_delivery")
        if (
            db == rb
            and dd == rd
            and ie is not None
            and idel is not None
            and ie != idel
            and receipt.get("reported_state") == "ACCEPTED"
        ):
            return {
                "judge": "PASS",
                "reason_code": "DECLARED_EQ_RECV_OK",
                "detail": {"bytes": db, "digest": dd},
            }
        if ie is not None and idel is not None and ie == idel:
            return {
                "judge": "FAIL",
                "reason_code": "NOT_INDEPENDENT",
                "detail": {"issuer": ie},
            }

    return {
        "judge": "UNKNOWN",
        "reason_code": "UNHANDLED",
        "detail": {"kind": kind},
    }


# Concrete CJK pair: raw "测" (3 UTF-8 bytes) vs JSON \\u6d4b escape (6 ASCII bytes)
RAW_CJK = "测"
ESC_CJK = "\\u6d4b"
assert len(RAW_CJK.encode("utf-8")) == 3
assert len(ESC_CJK.encode("utf-8")) == 6

# Equal-len different digest pair (40 bytes each)
A_BYTES = (b"a" * 19) + b"\n" + (b"a" * 19) + b"\n"
B_BYTES = (b"a" * 39) + b"\n"
assert len(A_BYTES) == len(B_BYTES) == 40
assert _sha(A_BYTES) != _sha(B_BYTES)


FIXTURES = [
    {
        "case_id": "DSH-CJK-ESCAPE-INFLATE-MUST-RED",
        "receipt": {
            "kind": "cjk_inflate_false_ok",
            "raw_text": RAW_CJK,
            "escape_form": ESC_CJK,
            "claimed_ok": True,
            "reported_state": "ACCEPTED",
        },
        "expect": "CJK_ESCAPE_BYTE_INFLATE",
    },
    {
        "case_id": "DSH-CJK-ESCAPE-INFLATE-HONEST",
        "receipt": {
            "kind": "cjk_inflate_honest",
            "raw_text": RAW_CJK,
            "escape_form": ESC_CJK,
            "claimed_ok": False,
            "recorded_state": "TRUNCATED",
            "payload_declared_bytes": 3,
            "receiver_computed_bytes": 6,
        },
        "expect": "CJK_ESCAPE_BYTE_INFLATE",
    },
    {
        "case_id": "DSH-EQUAL-LEN-DIFF-DIGEST-MUST-RED",
        "receipt": {
            "kind": "equal_len_diff",
            "raw_a": A_BYTES.decode("latin-1"),
            "raw_b": B_BYTES.decode("latin-1"),
            "size_equal": True,
            "digest_equal": False,
            "claimed_ok": True,
            "reported_state": "ACCEPTED",
        },
        "expect": "EQUAL_LEN_DIFF_DIGEST",
    },
    {
        "case_id": "DSH-EQUAL-LEN-DIFF-DIGEST-HONEST",
        "receipt": {
            "kind": "equal_len_honest",
            "raw_a": A_BYTES.decode("latin-1"),
            "raw_b": B_BYTES.decode("latin-1"),
            "size_equal": True,
            "digest_equal": False,
            "claimed_ok": False,
            "recorded_state": "CORRUPTED",
        },
        "expect": "EQUAL_LEN_DIFF_DIGEST",
    },
    {
        "case_id": "DSH-RECEIPT-HALF-TRUNC-MUST-UNKNOWN",
        "receipt": {
            "kind": "half_trunc_false_ok",
            "receipt_truncated": True,
            "claimed_ok": True,
            "reported_state": "ACCEPTED",
        },
        "expect": "RECEIPT_HALF_TRUNC_UNKNOWN",
    },
    {
        "case_id": "DSH-RECEIPT-HALF-TRUNC-HONEST",
        "receipt": {
            "kind": "half_trunc_honest",
            "receipt_truncated": True,
            "claimed_ok": False,
            "recorded_state": "UNKNOWN",
            "reason_code": "RECEIPT_HALF_TRUNC_UNKNOWN",
        },
        "expect": "RECEIPT_HALF_TRUNC_UNKNOWN",
    },
    {
        "case_id": "DSH-DECLARED-EQ-RECV-OK",
        "receipt": {
            "kind": "declared_eq_recv",
            "payload_declared_bytes": 40,
            "receiver_computed_bytes": 40,
            "payload_declared_digest": _sha(A_BYTES),
            "receiver_computed_digest": _sha(A_BYTES),
            "issuer_exec": "exec-side",
            "issuer_delivery": "recv-side",
            "reported_state": "ACCEPTED",
        },
        "expect": "DECLARED_EQ_RECV_OK",
    },
    {
        "case_id": "DSH-SAME-ISSUER-NOT-INDEPENDENT",
        "receipt": {
            "kind": "same_issuer",
            "issuer_exec": "same-party",
            "issuer_delivery": "same-party",
            "claimed_independent": True,
            "payload_declared_bytes": 40,
            "receiver_computed_bytes": 40,
            "payload_declared_digest": _sha(A_BYTES),
            "receiver_computed_digest": _sha(A_BYTES),
            "reported_state": "ACCEPTED",
        },
        "expect": "NOT_INDEPENDENT",
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
        "version": "CJK_ESCAPE_BYTE_INFLATE/v0.1",
        "all_match": ok,
        "n": len(rows),
        "n_match": sum(1 for r in rows if r["match"]),
        "rows": rows,
        "credits": [
            "DeepSeek-Harness (FOUR_STATE + dual receipt field-lock; three negctrl shapes CJK_ESCAPE / EQUAL_LEN_DIFF / HALF_TRUNC)",
            "Grok Bot (impl + must-fail samples)",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
