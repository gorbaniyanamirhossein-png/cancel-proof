#!/usr/bin/env python3
"""Validate Cancel-Proof receipts against cancel-receipt.schema.json.

Usage:
    python3 validate.py [FILE ...]     validate one or more receipt files
    python3 validate.py                validate examples/ in this directory
    python3 validate.py --selftest     run the built-in test suite

Validation is two layers:
  1. JSON Schema (via `jsonschema` when installed; a small stdlib fallback
     covering the core rules otherwise).
  2. Semantic checks the schema cannot express: dates not in the future,
     created_utc not before the cancellation, charges dated after the
     cancellation, receipt-year match, and a scan for secret-looking data
     (a receipt containing card-like digits is non-conforming per the spec).

Licence: Apache 2.0.
"""

import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "cancel-receipt.schema.json"
EXAMPLES_DIR = HERE / "examples"

SKEW = timedelta(minutes=5)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CARD_LIKE = re.compile(r"\d{13,19}")
RECEIPT_ID = re.compile(r"^CPR-([0-9]{4})-[A-Z0-9]{4,12}$")

try:
    import jsonschema

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover - fallback for bare Python installs
    HAVE_JSONSCHEMA = False


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- schema layer

def _fallback_schema_errors(data):
    """Minimal stdlib re-implementation of the schema's core rules.

    Used only when `jsonschema` is not installed. Returns a list of errors.
    """
    errors = []
    if not isinstance(data, dict):
        return ["receipt must be a JSON object"]
    for field in ("format", "version", "receipt_id", "issuer", "service",
                  "account", "cancellation", "created_utc"):
        if field not in data:
            errors.append(f"missing required field: {field}")
    if data.get("format") != "cancel-proof":
        errors.append("format must be 'cancel-proof'")
    if data.get("version") != "0.1":
        errors.append("version must be '0.1'")
    rid = data.get("receipt_id", "")
    if not isinstance(rid, str) or not RECEIPT_ID.match(rid):
        errors.append(f"receipt_id malformed: {rid!r}")
    if data.get("issuer") not in ("consumer", "seller"):
        errors.append(f"issuer must be 'consumer' or 'seller': {data.get('issuer')!r}")
    svc = data.get("service")
    if isinstance(svc, dict):
        if not svc.get("name") or not svc.get("domain"):
            errors.append("service requires name and domain")
    acct = data.get("account")
    if isinstance(acct, dict):
        if acct.get("type") not in ("email_partial", "email_hash",
                                    "account_partial", "phone_partial",
                                    "username_partial", "none"):
            errors.append(f"unknown account.type: {acct.get('type')!r}")
        if acct.get("type") == "email_hash":
            v = acct.get("value", "")
            if not isinstance(v, str) or not HEX64.match(v):
                errors.append("account.value must be a 64-hex SHA-256 for email_hash")
        if acct.get("type") == "none" and "value" in acct:
            errors.append("account.value must be absent when type is 'none'")
    canc = data.get("cancellation")
    if isinstance(canc, dict):
        if canc.get("method") not in ("link", "button", "chat", "phone",
                                      "in_person", "email", "other"):
            errors.append(f"unknown cancellation.method: {canc.get('method')!r}")
        if "datetime_utc" not in canc:
            errors.append("cancellation.datetime_utc is required")
    ev = data.get("evidence")
    has_ref = isinstance(canc, dict) and bool(canc.get("reference"))
    has_hash = (isinstance(ev, dict) and isinstance(ev.get("screenshot_sha256"), str)
                and HEX64.match(ev["screenshot_sha256"]))
    if isinstance(ev, dict) and "screenshot_sha256" in ev and not has_hash:
        errors.append("evidence.screenshot_sha256 must be 64 lowercase hex chars")
    if not has_ref and not has_hash:
        errors.append("receipt needs a reference number or a screenshot hash")
    flags = data.get("dark_pattern_flags", [])
    allowed = {"hidden_cancel_button", "forced_chat", "forced_call",
               "save_offer_wall", "confirm_shaming", "no_confirmation",
               "roach_motel"}
    if isinstance(flags, list):
        for flag in flags:
            if flag not in allowed:
                errors.append(f"unknown dark_pattern_flags entry: {flag!r}")
    for charge in data.get("charges_after_cancel", []) or []:
        if isinstance(charge, dict):
            cur = charge.get("currency", "")
            if not re.match(r"^[A-Z]{3}$", cur or ""):
                errors.append(f"charge currency must be an ISO 4217 code: {cur!r}")
    return errors


def schema_errors(data, schema):
    """Return a list of schema-validation error strings (empty = valid)."""
    if HAVE_JSONSCHEMA:
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker())
        return sorted(
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in validator.iter_errors(data)
        )
    return _fallback_schema_errors(data)


# -------------------------------------------------------------- semantic layer

def _parse_utc(value):
    """Parse an ISO 8601 UTC datetime; return None if unparsable."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def semantic_errors(data):
    """Checks the schema cannot express. Returns a list of errors."""
    errors = []
    now = datetime.now(timezone.utc)
    canc_dt = _parse_utc((data.get("cancellation") or {}).get("datetime_utc"))
    created_dt = _parse_utc(data.get("created_utc"))

    if canc_dt is not None and canc_dt > now + SKEW:
        errors.append("cancellation.datetime_utc is in the future")
    if created_dt is not None and created_dt > now + SKEW:
        errors.append("created_utc is in the future")
    if canc_dt is not None and created_dt is not None and created_dt + SKEW < canc_dt:
        errors.append("created_utc is earlier than cancellation.datetime_utc")

    rid = data.get("receipt_id", "")
    match = RECEIPT_ID.match(rid) if isinstance(rid, str) else None
    if match and created_dt is not None and match.group(1) != f"{created_dt.year:04d}":
        errors.append("receipt_id year does not match the year of created_utc")

    canc_date = canc_dt.date() if canc_dt else None
    for i, charge in enumerate(data.get("charges_after_cancel") or []):
        if not isinstance(charge, dict):
            continue
        try:
            charge_date = datetime.fromisoformat(charge.get("date", "")).date()
        except ValueError:
            errors.append(f"charges_after_cancel[{i}].date is not a valid date")
            continue
        if canc_date and charge_date <= canc_date:
            errors.append(
                f"charges_after_cancel[{i}].date is not after the cancellation")

    # Secret scan: card-like digit runs must not appear in a public receipt.
    # The screenshot hash and email hash are excluded (hex can contain digits).
    def scan(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("screenshot_sha256",):
                    continue
                if key == "value" and obj.get("type") == "email_hash":
                    continue
                scan(value, f"{path}.{key}" if path else key)
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                scan(value, f"{path}[{i}]")
        elif isinstance(obj, str) and CARD_LIKE.search(obj):
            errors.append(
                f"{path}: contains a card-like digit run — "
                "receipts must not contain card or account numbers")
    scan(data)
    return errors


def validate_receipt(data, schema):
    """Full validation. Returns a list of error strings (empty = valid)."""
    return schema_errors(data, schema) + semantic_errors(data)


# ---------------------------------------------------------------------- CLI

def validate_file(path, schema):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read/parse: {exc}"]
    return validate_receipt(data, schema)


def _selftest():
    """Built-in test suite. Returns (passed, failed) counts."""
    schema = load_schema()
    passed = failed = 0

    def check(name, data, expect_valid):
        nonlocal passed, failed
        errs = validate_receipt(data, schema)
        ok = (not errs) if expect_valid else bool(errs)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  (errors: {errs})"))
        if ok:
            passed += 1
        else:
            failed += 1

    print("self-test: examples must validate")
    base = {}
    for name in ("receipt-clean-cancel.json", "receipt-wrongful-charge.json"):
        with open(EXAMPLES_DIR / name, encoding="utf-8") as f:
            base[name] = json.load(f)
        check(f"example {name} is valid", base[name], True)
    clean = base["receipt-clean-cancel.json"]

    print("self-test: minimal receipts must validate")
    ref_only = copy.deepcopy(clean)
    ref_only.pop("evidence")
    check("reference only, no screenshot", ref_only, True)
    hash_only = copy.deepcopy(clean)
    hash_only["cancellation"] = {k: v for k, v in clean["cancellation"].items()
                                 if k != "reference"}
    check("screenshot hash only, no reference", hash_only, True)

    print("self-test: tampered receipts must fail")
    cases = []

    def tampered(name, mutate):
        d = copy.deepcopy(clean)
        mutate(d)
        cases.append((name, d))

    tampered("missing service.domain",
             lambda d: d["service"].pop("domain"))
    tampered("screenshot hash too short",
             lambda d: d["evidence"].update(
                 screenshot_sha256="71ca83ae39a50af48be3284ef0a44e5b3119d1"))
    tampered("neither reference nor screenshot hash",
             lambda d: (d["cancellation"].pop("reference"), d.pop("evidence")))
    tampered("malformed receipt_id",
             lambda d: d.update(receipt_id="CPR-2026-x"))
    tampered("email_hash with non-hex value",
             lambda d: d.update(account={"type": "email_hash",
                                         "value": "not-a-hash"}))
    tampered("unknown dark-pattern flag",
             lambda d: d.update(dark_pattern_flags=["mind_control"]))
    tampered("cancellation in the future",
             lambda d: d["cancellation"].update(
                 datetime_utc="2999-01-01T00:00:00Z"))
    tampered("bad currency code",
             lambda d: d.update(charges_after_cancel=[
                 {"date": "2026-11-22", "amount": 9.99, "currency": "US"}]))
    tampered("wrong format const",
             lambda d: d.update(format="cancelproof"))
    tampered("created before cancellation",
             lambda d: d.update(created_utc="2026-11-20T00:00:00Z"))
    tampered("charge dated before cancellation",
             lambda d: d.update(charges_after_cancel=[
                 {"date": "2026-11-20", "amount": 9.99, "currency": "USD"}]))
    tampered("card-like digits in notes",
             lambda d: d.update(notes="my card 4111111111111111 was charged"))
    tampered("account none with a value",
             lambda d: d.update(account={"type": "none",
                                         "value": "someone@example.com"}))
    for name, data in cases:
        check(name, data, False)

    print(f"self-test: {passed} passed, {failed} failed "
          f"(jsonschema {'available' if HAVE_JSONSCHEMA else 'fallback'})")
    return passed, failed


def main(argv):
    if "--selftest" in argv:
        _, failed = _selftest()
        return 1 if failed else 0
    schema = load_schema()
    paths = [Path(a) for a in argv[1:] if not a.startswith("-")]
    if not paths:
        paths = sorted(EXAMPLES_DIR.glob("*.json"))
    overall_ok = True
    for path in paths:
        errs = validate_file(path, schema)
        if errs:
            overall_ok = False
            print(f"FAIL  {path}")
            for err in errs:
                print(f"      - {err}")
        else:
            print(f"OK    {path}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
