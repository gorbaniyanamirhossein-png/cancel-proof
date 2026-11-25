#!/usr/bin/env python3
"""Validate Cancel-Proof receipts against cancel-receipt.schema.json.

Usage:
    python3 validate.py [FILE ...]     validate one or more receipt files
    python3 validate.py                validate examples/ in this directory
    python3 validate.py --selftest     run the built-in test suite
                                       (examples + tests/ fixtures + a
                                       jsonschema/fallback parity check)

Accepts receipts written as version 0.1 or 0.2 (see
CANCEL-PROOF-SPEC-v0.2.md). Version 0.1 files are never modified by v0.2.

Validation is two layers:
  1. JSON Schema (via `jsonschema` when installed; a stdlib fallback
     covering all schema rules otherwise — the self-test checks both
     layers agree on every fixture in tests/).
  2. Semantic checks the schema cannot express: dates not in the future,
     created_utc not before the cancellation, charges dated after the
     cancellation date, receipt-year match, amount rules, and a scan for
     secret-looking data (a receipt containing card-like digits or a full
     email address is non-conforming per the spec).

Every error carries a stable code from the catalogue in
CANCEL-PROOF-SPEC-v0.2.md, section 6 (E_MISSING_FIELD, E_BAD_HASH,
E_NO_EVIDENCE, ...). The same codes are used by the Verify tab of
index.html.

Signatures: a receipt carrying `signature` is verified (ECDSA P-256 over
the JCS canonical form, RFC 8785) when the `cryptography` package is
installed. When it is not installed, the signature is NOT verified and a
NOTE is reported instead of an error — never silently pass it.

Licence: Apache 2.0.
"""

import base64
import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "cancel-receipt.schema.json"
EXAMPLES_DIR = HERE / "examples"
TESTS_DIR = HERE / "tests"

SKEW = timedelta(minutes=5)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CARD_LIKE = re.compile(r"\d{13,19}")
EMAIL_LIKE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RECEIPT_ID = re.compile(r"^CPR-([0-9]{4})-[A-Z0-9]{4,12}$")
DATETIME_Z = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$")
DATE_ONLY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
B64URL43 = re.compile(r"^[A-Za-z0-9_-]{43}$")
B64URL86 = re.compile(r"^[A-Za-z0-9_-]{86}$")
HOSTNAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$")

# ISO 4217 alphabetic codes for currencies in current circulation
# (plus XAU/XAG/XPT precious metals and XDR Special Drawing Rights).
# BTC, USDT and other crypto codes are NOT ISO 4217 and are rejected.
ISO_4217 = frozenset(
    "AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD "
    "BND BOB BRL BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE "
    "CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF "
    "GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS "
    "KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD "
    "MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR "
    "PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK "
    "SGD SHP SLE SOS SRD SSP STN SYP SZL THB TJS TMT TND TOP TRY TTD TWD "
    "TZS UAH UGX USD UYU UZS VED VES VND VUV WST XAF XAG XAU XCD XDR XOF "
    "XPF XPT YER ZAR ZMW ZWL".split()
)

METHODS = {"link", "button", "chat", "phone", "in_person", "email", "other"}
ACCOUNT_TYPES = {"email_partial", "email_hash", "account_partial",
                 "phone_partial", "username_partial", "none"}
FLAGS = {"hidden_cancel_button", "forced_chat", "forced_call",
         "save_offer_wall", "confirm_shaming", "no_confirmation",
         "roach_motel"}
STATUSES = {"no_charge", "charged_refunded", "charged_disputed",
            "charged_unresolved"}
EVIDENCE_ITEM_TYPES = {"email", "screenshot", "pdf", "reference", "response"}
SUPERSEDED_TYPES = {"seller_confirmation", "correction", "replacement"}

try:
    import jsonschema

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover - fallback for bare Python installs
    HAVE_JSONSCHEMA = False


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _err(code, msg):
    return f"{code}: {msg}"


# ---------------------------------------------------------------- schema layer

def _is_datetime_z(value):
    return isinstance(value, str) and bool(DATETIME_Z.match(value))


def _is_date(value):
    if not isinstance(value, str) or not DATE_ONLY.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _check_no_extra(obj, allowed, errors, where, code="E_BAD_VALUE"):
    if isinstance(obj, dict):
        for key in obj:
            if key not in allowed:
                errors.append(_err(code, f"{where}: unexpected field '{key}'"))


def _fallback_schema_errors(data):
    """Stdlib re-implementation of every rule in the schema.

    Used when `jsonschema` is not installed, and by the self-test parity
    check. Returns a list of coded errors (empty = valid).
    """
    errors = []
    if not isinstance(data, dict):
        return [_err("E_BAD_VALUE", "receipt must be a JSON object")]
    _check_no_extra(data, {"format", "version", "receipt_id", "issuer",
                           "service", "account", "cancellation", "evidence",
                           "dark_pattern_flags", "charges_after_cancel",
                           "superseded_by", "notes", "created_utc",
                           "signature", "status"}, errors, "receipt")
    for field in ("format", "version", "receipt_id", "issuer", "service",
                  "account", "cancellation", "created_utc"):
        if field not in data:
            errors.append(_err("E_MISSING_FIELD",
                               f"missing required field: {field}"))
    if data.get("format") not in (None, "cancel-proof"):
        errors.append(_err("E_BAD_VALUE", "format must be 'cancel-proof'"))
    if data.get("version") not in (None, "0.1", "0.2"):
        errors.append(_err("E_UNSUPPORTED_VERSION",
                           f"unsupported version: {data.get('version')!r}"))
    rid = data.get("receipt_id", "")
    if "receipt_id" in data and (
            not isinstance(rid, str) or not RECEIPT_ID.match(rid)):
        errors.append(_err("E_BAD_VALUE", f"receipt_id malformed: {rid!r}"))
    if data.get("issuer") not in (None, "consumer", "seller"):
        errors.append(_err("E_BAD_VALUE",
                           f"issuer must be 'consumer' or 'seller': "
                           f"{data.get('issuer')!r}"))
    svc = data.get("service")
    if isinstance(svc, dict):
        _check_no_extra(svc, {"name", "domain"}, errors, "service")
        if "name" not in svc or not isinstance(svc.get("name"), str) \
                or not svc.get("name"):
            errors.append(_err("E_MISSING_FIELD",
                               "service requires a name"))
        if "domain" not in svc:
            errors.append(_err("E_MISSING_FIELD",
                               "service requires a domain"))
        elif not isinstance(svc.get("domain"), str) \
                or not HOSTNAME.match(svc["domain"]) \
                or len(svc["domain"]) > 253:
            errors.append(_err("E_BAD_VALUE",
                               f"service.domain is not a valid hostname: "
                               f"{svc.get('domain')!r}"))
    elif "service" in data:
        errors.append(_err("E_BAD_VALUE", "service must be an object"))
    acct = data.get("account")
    if isinstance(acct, dict):
        _check_no_extra(acct, {"type", "value"}, errors, "account")
        if acct.get("type") not in ACCOUNT_TYPES:
            errors.append(_err("E_BAD_VALUE",
                               f"unknown account.type: {acct.get('type')!r}"))
        if acct.get("type") == "email_hash":
            v = acct.get("value", "")
            if not isinstance(v, str) or not HEX64.match(v):
                errors.append(_err(
                    "E_BAD_HASH",
                    "account.value must be a 64-hex SHA-256 for email_hash"))
        if acct.get("type") == "none" and "value" in acct:
            errors.append(_err("E_BAD_VALUE",
                               "account.value must be absent when type is "
                               "'none'"))
    elif "account" in data:
        errors.append(_err("E_BAD_VALUE", "account must be an object"))
    canc = data.get("cancellation")
    if isinstance(canc, dict):
        _check_no_extra(canc, {"datetime_utc", "effective_at", "method",
                               "reference"}, errors, "cancellation")
        if canc.get("method") not in METHODS:
            errors.append(_err(
                "E_BAD_VALUE",
                f"unknown cancellation.method: {canc.get('method')!r}"))
        if "datetime_utc" not in canc:
            errors.append(_err("E_MISSING_FIELD",
                               "cancellation.datetime_utc is required"))
        elif not _is_datetime_z(canc["datetime_utc"]):
            errors.append(_err(
                "E_BAD_VALUE",
                "cancellation.datetime_utc must be ISO 8601 UTC, Zulu form"))
        if "effective_at" in canc and not _is_datetime_z(canc["effective_at"]):
            errors.append(_err(
                "E_BAD_VALUE",
                "cancellation.effective_at must be ISO 8601 UTC, Zulu form"))
    elif "cancellation" in data:
        errors.append(_err("E_BAD_VALUE", "cancellation must be an object"))
    ev = data.get("evidence")
    has_ref = isinstance(canc, dict) and bool(canc.get("reference"))
    has_hash = False
    has_items = False
    if isinstance(ev, dict):
        _check_no_extra(ev, {"screenshot_sha256", "screenshot_filename",
                             "items"}, errors, "evidence")
        if "screenshot_sha256" in ev:
            if isinstance(ev["screenshot_sha256"], str) \
                    and HEX64.match(ev["screenshot_sha256"]):
                has_hash = True
            else:
                errors.append(_err(
                    "E_BAD_HASH",
                    "evidence.screenshot_sha256 must be 64 lowercase hex "
                    "characters"))
        items = ev.get("items")
        if items is not None:
            if not isinstance(items, list) or not items:
                errors.append(_err(
                    "E_NO_EVIDENCE",
                    "evidence.items must be a non-empty array"))
            else:
                has_items = True
                for i, item in enumerate(items):
                    where = f"evidence.items[{i}]"
                    if not isinstance(item, dict):
                        errors.append(_err("E_BAD_VALUE",
                                           f"{where} must be an object"))
                        continue
                    _check_no_extra(
                        item, {"type", "hash", "ref", "received_utc",
                               "source"}, errors, where)
                    if item.get("type") not in EVIDENCE_ITEM_TYPES:
                        errors.append(_err(
                            "E_BAD_VALUE",
                            f"{where}: unknown type {item.get('type')!r}"))
                    if "hash" in item and (
                            not isinstance(item["hash"], str)
                            or not HEX64.match(item["hash"])):
                        errors.append(_err(
                            "E_BAD_HASH",
                            f"{where}.hash must be 64 lowercase hex "
                            "characters"))
                    if "received_utc" in item \
                            and not _is_datetime_z(item["received_utc"]):
                        errors.append(_err(
                            "E_BAD_VALUE",
                            f"{where}.received_utc must be ISO 8601 UTC, "
                            "Zulu form"))
                    if "hash" not in item and "ref" not in item:
                        errors.append(_err(
                            "E_BAD_VALUE",
                            f"{where} needs a hash or a ref"))
    elif "evidence" in data:
        errors.append(_err("E_BAD_VALUE", "evidence must be an object"))
    if not has_ref and not has_hash and not has_items:
        errors.append(_err(
            "E_NO_EVIDENCE",
            "receipt needs a reference number, a screenshot hash, or a "
            "non-empty evidence.items list"))
    flags = data.get("dark_pattern_flags")
    if flags is not None:
        if not isinstance(flags, list):
            errors.append(_err("E_BAD_VALUE",
                               "dark_pattern_flags must be an array"))
        else:
            for flag in flags:
                if flag not in FLAGS:
                    errors.append(_err("E_UNKNOWN_FLAG",
                                       f"unknown dark_pattern_flags entry: "
                                       f"{flag!r}"))
            if len(set(flags)) != len(flags):
                errors.append(_err("E_BAD_VALUE",
                                   "dark_pattern_flags must not repeat"))
    for i, charge in enumerate(data.get("charges_after_cancel") or []):
        where = f"charges_after_cancel[{i}]"
        if not isinstance(charge, dict):
            errors.append(_err("E_BAD_VALUE", f"{where} must be an object"))
            continue
        _check_no_extra(charge, {"date", "amount", "amount_minor",
                                 "currency", "note"}, errors, where)
        if "date" not in charge:
            errors.append(_err("E_MISSING_FIELD", f"{where}.date is required"))
        elif not _is_date(charge["date"]):
            errors.append(_err("E_BAD_VALUE",
                               f"{where}.date is not a valid date"))
        if "currency" not in charge:
            errors.append(_err("E_MISSING_FIELD",
                               f"{where}.currency is required"))
        elif charge["currency"] not in ISO_4217:
            errors.append(_err(
                "E_BAD_CURRENCY",
                f"{where}.currency is not an ISO 4217 code: "
                f"{charge['currency']!r}"))
        amt, minor = charge.get("amount"), charge.get("amount_minor")
        if amt is None and minor is None:
            errors.append(_err(
                "E_BAD_AMOUNT",
                f"{where} needs amount or amount_minor"))
        if amt is not None:
            if not isinstance(amt, (int, float)) or isinstance(amt, bool) \
                    or amt <= 0:
                errors.append(_err("E_BAD_AMOUNT",
                                   f"{where}.amount must be a number > 0"))
            elif round(amt, 2) != amt:
                errors.append(_err(
                    "E_BAD_AMOUNT",
                    f"{where}.amount has more than 2 decimal places "
                    "(use amount_minor for exact amounts)"))
        if minor is not None:
            if not isinstance(minor, int) or isinstance(minor, bool) \
                    or minor < 1:
                errors.append(_err(
                    "E_BAD_AMOUNT",
                    f"{where}.amount_minor must be a positive integer"))
    if "created_utc" in data and not _is_datetime_z(data["created_utc"]):
        errors.append(_err("E_BAD_VALUE",
                           "created_utc must be ISO 8601 UTC, Zulu form"))
    if "notes" in data and (not isinstance(data["notes"], str)
                            or len(data["notes"]) > 500):
        errors.append(_err("E_BAD_VALUE",
                           "notes must be a string of at most 500 characters"))
    if "status" in data and data["status"] not in STATUSES:
        errors.append(_err("E_BAD_STATUS",
                           f"unknown status: {data['status']!r}"))
    sup = data.get("superseded_by")
    if sup is not None:
        if isinstance(sup, str):
            if len(sup) > 200:
                errors.append(_err("E_BAD_SUPERSEDED",
                                   "superseded_by string is too long"))
        elif isinstance(sup, dict):
            _check_no_extra(sup, {"receipt_id", "type", "date", "note"},
                            errors, "superseded_by", code="E_BAD_SUPERSEDED")
            if not isinstance(sup.get("receipt_id"), str) \
                    or not RECEIPT_ID.match(sup.get("receipt_id", "")):
                errors.append(_err(
                    "E_BAD_SUPERSEDED",
                    "superseded_by.receipt_id is malformed"))
            if sup.get("type") not in SUPERSEDED_TYPES:
                errors.append(_err(
                    "E_BAD_SUPERSEDED",
                    f"unknown superseded_by.type: {sup.get('type')!r}"))
            if "date" in sup and not _is_date(sup["date"]):
                errors.append(_err("E_BAD_SUPERSEDED",
                                   "superseded_by.date is not a valid date"))
        else:
            errors.append(_err(
                "E_BAD_SUPERSEDED",
                "superseded_by must be a string (v0.1) or an object (v0.2)"))
    sig = data.get("signature")
    if sig is not None:
        if not isinstance(sig, dict):
            errors.append(_err("E_BAD_SIGNATURE",
                               "signature must be an object"))
        else:
            _check_no_extra(sig, {"algorithm", "public_key", "signature",
                                  "key_url"}, errors, "signature",
                            code="E_BAD_SIGNATURE")
            if sig.get("algorithm") != "ES256-JCS":
                errors.append(_err("E_BAD_SIGNATURE",
                                   "signature.algorithm must be 'ES256-JCS'"))
            pk = sig.get("public_key")
            if not isinstance(pk, dict):
                errors.append(_err("E_BAD_SIGNATURE",
                                   "signature.public_key must be an object"))
            else:
                _check_no_extra(pk, {"kty", "crv", "x", "y"}, errors,
                                "signature.public_key",
                                code="E_BAD_SIGNATURE")
                if pk.get("kty") != "EC" or pk.get("crv") != "P-256":
                    errors.append(_err(
                        "E_BAD_SIGNATURE",
                        "signature.public_key must be a P-256 EC JWK"))
                for coord in ("x", "y"):
                    if not isinstance(pk.get(coord), str) \
                            or not B64URL43.match(pk.get(coord, "")):
                        errors.append(_err(
                            "E_BAD_SIGNATURE",
                            f"signature.public_key.{coord} must be 43 "
                            "base64url characters"))
            if not isinstance(sig.get("signature"), str) \
                    or not B64URL86.match(sig.get("signature", "")):
                errors.append(_err(
                    "E_BAD_SIGNATURE",
                    "signature.signature must be 86 base64url characters"))
            if "key_url" in sig and (
                    not isinstance(sig["key_url"], str)
                    or not re.match(r"^https?://\S+$", sig["key_url"])):
                errors.append(_err("E_BAD_SIGNATURE",
                                   "signature.key_url must be an http(s) URL"))
    return errors


def _code_for_jsonschema_error(err):
    """Map a jsonschema error to the spec's error-code catalogue."""
    path = list(err.path)
    last = path[-1] if path else None
    if err.validator == "required":
        return "E_MISSING_FIELD"
    if err.validator == "const":
        if last == "version":
            return "E_UNSUPPORTED_VERSION"
        if last == "algorithm":
            return "E_BAD_SIGNATURE"
        return "E_BAD_VALUE"
    if err.validator == "enum":
        if last == "status":
            return "E_BAD_STATUS"
        if path and path[0] == "dark_pattern_flags":
            return "E_UNKNOWN_FLAG"
        if last == "version":
            return "E_UNSUPPORTED_VERSION"
        if last == "type" and path and path[0] == "superseded_by":
            return "E_BAD_SUPERSEDED"
        return "E_BAD_VALUE"
    if err.validator == "pattern":
        if last in ("screenshot_sha256", "hash"):
            return "E_BAD_HASH"
        if last == "value" and path and path[0] == "account":
            return "E_BAD_HASH"
        if last == "currency":
            return "E_BAD_CURRENCY"
        if last in ("signature", "x", "y"):
            return "E_BAD_SIGNATURE"
        if path and path[0] == "superseded_by":
            return "E_BAD_SUPERSEDED"
        return "E_BAD_VALUE"
    if err.validator == "anyOf":
        if not path:
            return "E_NO_EVIDENCE"
        if path and path[0] == "charges_after_cancel":
            return "E_BAD_AMOUNT"
        if path and path[0] == "superseded_by":
            return "E_BAD_SUPERSEDED"
        return "E_BAD_VALUE"
    if err.validator == "minItems":
        return "E_NO_EVIDENCE"
    if err.validator in ("exclusiveMinimum", "minimum"):
        return "E_BAD_AMOUNT"
    if err.validator == "type" and last in ("amount", "amount_minor"):
        return "E_BAD_AMOUNT"
    return "E_BAD_VALUE"


def schema_errors(data, schema, use_jsonschema=True):
    """Return a list of coded schema-validation errors (empty = valid)."""
    if use_jsonschema and HAVE_JSONSCHEMA:
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker())
        out = []
        for e in validator.iter_errors(data):
            code = _code_for_jsonschema_error(e)
            where = "/".join(str(p) for p in e.path) or "<root>"
            out.append(_err(code, f"{where}: {e.message}"))
        return sorted(out)
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
    """Checks the schema cannot express. Returns coded errors."""
    errors = []
    now = datetime.now(timezone.utc)
    canc = data.get("cancellation") or {}
    canc_dt = _parse_utc(canc.get("datetime_utc"))
    eff_dt = _parse_utc(canc.get("effective_at"))
    created_dt = _parse_utc(data.get("created_utc"))

    if canc_dt is not None and canc_dt > now + SKEW:
        errors.append(_err("E_FUTURE_DATE",
                           "cancellation.datetime_utc is in the future"))
    if created_dt is not None and created_dt > now + SKEW:
        errors.append(_err("E_FUTURE_DATE", "created_utc is in the future"))
    # effective_at is NOT checked for being in the future: a cancellation
    # requested now routinely takes effect later (end of the paid period).
    if canc_dt is not None and created_dt is not None \
            and created_dt + SKEW < canc_dt:
        errors.append(_err(
            "E_CREATED_BEFORE_CANCEL",
            "created_utc is earlier than cancellation.datetime_utc"))
    if canc_dt is not None and eff_dt is not None and eff_dt < canc_dt:
        errors.append(_err(
            "E_EFFECTIVE_DATE",
            "cancellation.effective_at is earlier than "
            "cancellation.datetime_utc"))
    if isinstance(canc.get("reference"), str) and not canc["reference"].strip():
        errors.append(_err("E_BAD_VALUE",
                           "cancellation.reference must not be blank"))

    rid = data.get("receipt_id", "")
    match = RECEIPT_ID.match(rid) if isinstance(rid, str) else None
    if match and created_dt is not None \
            and match.group(1) != f"{created_dt.year:04d}":
        errors.append(_err(
            "E_RECEIPT_YEAR",
            "receipt_id year does not match the year of created_utc"))

    # Charges are date-only, so the comparison is against the cancellation
    # DATE: a same-day charge cannot be proven to be after the cancellation
    # time, so it does not count as "after cancellation" (spec section 4).
    canc_date = canc_dt.date() if canc_dt else None
    for i, charge in enumerate(data.get("charges_after_cancel") or []):
        if not isinstance(charge, dict):
            continue
        try:
            charge_date = datetime.fromisoformat(charge.get("date", "")).date()
        except ValueError:
            errors.append(_err(
                "E_BAD_VALUE",
                f"charges_after_cancel[{i}].date is not a valid date"))
            continue
        if canc_date and charge_date <= canc_date:
            errors.append(_err(
                "E_CHARGE_DATE",
                f"charges_after_cancel[{i}].date is not after the "
                "cancellation date"))
        amt = charge.get("amount")
        if isinstance(amt, (int, float)) and not isinstance(amt, bool):
            if round(amt, 2) != amt:
                errors.append(_err(
                    "E_BAD_AMOUNT",
                    f"charges_after_cancel[{i}].amount has more than 2 "
                    "decimal places (use amount_minor for exact amounts)"))
        if isinstance(charge.get("currency"), str) \
                and charge["currency"] not in ISO_4217:
            errors.append(_err(
                "E_BAD_CURRENCY",
                f"charges_after_cancel[{i}].currency is not an ISO 4217 "
                f"code: {charge['currency']!r}"))

    # Secret scan: card-like digit runs and full email addresses must not
    # appear in a public receipt. Excluded: hashes and signatures (hex /
    # base64url can contain long digit runs), and the seller's own
    # reference number and the receipt id (a 16-digit confirmation number
    # is not a card number).
    def scan(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("screenshot_sha256", "signature", "hash",
                           "x", "y"):
                    continue
                if key == "value" and obj.get("type") == "email_hash":
                    continue
                if path == "" and key in ("receipt_id",):
                    continue
                if path == "cancellation" and key == "reference":
                    continue
                scan(value, f"{path}.{key}" if path else key)
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                scan(value, f"{path}[{i}]")
        elif isinstance(obj, str):
            if CARD_LIKE.search(obj):
                errors.append(_err(
                    "E_SECRET_DETECTED",
                    f"{path}: contains a card-like digit run — receipts "
                    "must not contain card or account numbers"))
            elif EMAIL_LIKE.search(obj):
                errors.append(_err(
                    "E_SECRET_DETECTED",
                    f"{path}: contains a full email address — receipts "
                    "must not contain full email addresses"))
    scan(data)
    return errors


# ------------------------------------------------------- signature verification

def _jcs_number(value):
    """Serialize a JSON number the way JCS (RFC 8785) does, i.e. the way
    ECMAScript Number::toString does. Integers and integral floats print
    without a fraction; other floats use Python's shortest repr with the
    exponent's leading zero removed (1e-07 -> 1e-7). Exotic floats outside
    everyday receipt values may still differ — signed receipts SHOULD use
    amount_minor (an integer) instead of amount (spec section 5)."""
    if isinstance(value, bool):
        raise TypeError("boolean is not a number here")
    if isinstance(value, int):
        return str(value)
    if value == 0:
        return "0"
    if value == int(value) and abs(value) < 1e21:
        return str(int(value))
    text = repr(value)
    if "e" in text:
        mantissa, exp = text.split("e")
        sign = "+" if exp.startswith("+") else ("-" if exp.startswith("-")
                                                else "")
        digits = exp.lstrip("+-").lstrip("0") or "0"
        return f"{mantissa}e{sign}{digits}"
    return text


def canonicalize(value):
    """JCS canonical form (RFC 8785) for the JSON values receipts use:
    object keys sorted by UTF-16 code units, no whitespace."""
    if value is None or isinstance(value, (str, bool)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return _jcs_number(value)
    if isinstance(value, list):
        return "[" + ",".join(canonicalize(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        return "{" + ",".join(
            json.dumps(k, ensure_ascii=False) + ":" + canonicalize(value[k])
            for k in keys) + "}"
    raise TypeError(f"cannot canonicalize {type(value)}")


def _b64url_decode(text):
    pad = (4 - (len(text) % 4)) % 4
    return base64.urlsafe_b64decode(text + "=" * pad)


def verify_signature(data):
    """Verify a receipt's `signature` field.

    Returns (status, message) with status one of 'absent' (no signature),
    'valid', 'invalid', or 'skipped' (cryptography package not installed —
    the signature was NOT verified).
    """
    sig = data.get("signature")
    if sig is None:
        return ("absent", "")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
    except ImportError:
        return ("skipped",
                "signature present but the 'cryptography' package is not "
                "installed — signature NOT verified")
    try:
        raw = _b64url_decode(sig["signature"])
        if len(raw) != 64:
            return ("invalid", "signature is not 64 bytes")
        pk = sig["public_key"]
        x = int.from_bytes(_b64url_decode(pk["x"]), "big")
        y = int.from_bytes(_b64url_decode(pk["y"]), "big")
        pub = ec.EllipticCurvePublicNumbers(
            x, y, ec.SECP256R1()).public_key()
        unsigned = {k: v for k, v in data.items() if k != "signature"}
        payload = canonicalize(unsigned).encode("utf-8")
        der = utils.encode_dss_signature(int.from_bytes(raw[:32], "big"),
                                         int.from_bytes(raw[32:], "big"))
        pub.verify(der, payload, ec.ECDSA(hashes.SHA256()))
        return ("valid", "signature valid (ECDSA P-256 over JCS canonical "
                         "form)")
    except InvalidSignature:
        return ("invalid", "signature does not match the receipt contents")
    except (ValueError, KeyError, TypeError) as exc:
        return ("invalid", f"signature malformed: {exc}")


def validate_receipt(data, schema):
    """Full validation. Returns (errors, notes): coded error strings and
    informational notes (e.g. a signature that could not be verified)."""
    errors = schema_errors(data, schema) + semantic_errors(data)
    notes = []
    status, message = verify_signature(data)
    if status == "invalid":
        errors.append(_err("E_BAD_SIGNATURE", message))
    elif status == "skipped":
        notes.append("NOTE: " + message)
    elif status == "valid":
        notes.append("NOTE: " + message)
    return errors, notes


# ---------------------------------------------------------------------- CLI

def validate_file(path, schema):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read/parse: {exc}"], []
    return validate_receipt(data, schema)


def _selftest():
    """Built-in test suite: examples, tests/ fixtures, and a
    jsonschema/fallback parity check. Returns (passed, failed)."""
    schema = load_schema()
    passed = failed = 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  ({detail})"))
        if ok:
            passed += 1
        else:
            failed += 1

    print("self-test: examples must validate (v0.1 and v0.2)")
    example_files = sorted(EXAMPLES_DIR.rglob("*.json"))
    for path in example_files:
        errs, _ = validate_file(path, schema)
        check(f"example {path.relative_to(HERE)} is valid", not errs,
              "; ".join(errs))

    print("self-test: tests/valid fixtures must validate")
    for path in sorted((TESTS_DIR / "valid").glob("*.json")):
        errs, _ = validate_file(path, schema)
        check(f"valid/{path.name}", not errs, "; ".join(errs))

    print("self-test: tests/invalid fixtures must fail with the expected code")
    code_re = re.compile(r"\.([A-Z][A-Z0-9_]*)\.json$")
    for path in sorted((TESTS_DIR / "invalid").glob("*.json")):
        match = code_re.search(path.name)
        expected = match.group(1) if match else None
        errs, _ = validate_file(path, schema)
        got_codes = {e.split(":", 1)[0] for e in errs}
        ok = bool(errs) and (expected is None or expected in got_codes)
        check(f"invalid/{path.name} (expect {expected})", ok,
              "; ".join(errs) or "no errors")

    print("self-test: jsonschema and stdlib fallback must agree (parity)")
    all_fixtures = example_files \
        + sorted((TESTS_DIR / "valid").glob("*.json")) \
        + sorted((TESTS_DIR / "invalid").glob("*.json"))
    mismatch = 0
    for path in all_fixtures:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        with_schema = schema_errors(data, schema, use_jsonschema=True)
        with_fallback = schema_errors(data, schema, use_jsonschema=False)
        # Some rules (ISO 4217 membership, max 2 decimals on amount) live
        # only in the shared semantic layer, so parity compares the FULL
        # verdict of each layer, not the schema layer alone.
        sem = semantic_errors(data)
        agree = bool(with_schema + sem) == bool(with_fallback + sem)
        if not agree:
            mismatch += 1
            print(f"    MISMATCH {path.name}: jsonschema={with_schema} "
                  f"fallback={with_fallback}")
    check(f"parity over {len(all_fixtures)} fixtures", mismatch == 0,
          f"{mismatch} mismatches")

    print("self-test: signature handling")
    signed = EXAMPLES_DIR / "v0.2" / "receipt-seller-signed.json"
    if signed.exists():
        with open(signed, encoding="utf-8") as f:
            data = json.load(f)
        status, _ = verify_signature(data)
        check("signed example verifies (or cleanly skips without "
              "cryptography)", status in ("valid", "skipped"),
              f"status={status}")
        tampered = copy.deepcopy(data)
        tampered["service"]["name"] = "Tampered Service"
        t_status, _ = verify_signature(tampered)
        check("tampered signed receipt fails verification (or skips)",
              t_status in ("invalid", "skipped"), f"status={t_status}")

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
        paths = sorted(EXAMPLES_DIR.rglob("*.json"))
    overall_ok = True
    for path in paths:
        errs, notes = validate_file(path, schema)
        if errs:
            overall_ok = False
            print(f"FAIL  {path}")
            for err in errs:
                print(f"      - {err}")
        else:
            print(f"OK    {path}")
        for note in notes:
            print(f"      {note}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
