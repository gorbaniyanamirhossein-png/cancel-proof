# Cancel-Proof — Shareable Cancellation Receipt Format

**Version:** 0.2 — 25 November 2026
**Status:** Draft for public comment
**Licence:** CC BY 4.0 (this document). Code (validator, page) is Apache 2.0.
**Author:** Amirhossein Gorbaniyan

**Changes from v0.1:** multi-item evidence, `effective_at`, seller
signatures (ES256-JCS), a `status` field, structured supersession,
`amount_minor`, a shared error-code catalogue, a salted email hash, and
the privacy and page fixes listed in the CHANGELOG. **Version 0.1
receipts remain valid** — this schema accepts `"0.1"` and `"0.2"`, and
v0.1 files in this repository are frozen unchanged.

## 1. The problem

When a consumer cancels a subscription, the proof of cancellation stays with
the seller. The consumer has no standard, portable, shareable record. When the
seller keeps charging — or denies the cancellation ever happened — the dispute
is the consumer's word against the seller's database. Chargebacks, complaints
to regulators, and press stories all fail for the same reason: no evidence the
consumer controls.

Cancel-Proof is a minimal, open format for a **cancellation receipt**: a small
JSON file the consumer creates at the moment of cancellation, can publish
anywhere, and anyone can verify. No server, no account, no fee.

## 2. Design principles

1. **Public by design.** A receipt is meant to be shared — posted, linked,
   attached to a complaint. Anything in it must be safe to publish.
2. **No secrets, ever.** A receipt MUST NOT contain passwords, full account
   numbers, card numbers, or full email addresses. Account identifiers are
   partial or hashed only (§4).
3. **Evidence, not claims.** A receipt must carry at least one verifiable
   piece of evidence: the seller's reference number, the SHA-256 hash of a
   screenshot of the cancellation confirmation, or a non-empty list of
   evidence items (§3).
4. **No infrastructure.** Receipts are plain files. They are created and
   verified in the browser, offline, on a phone.
5. **Registry-ready.** Receipts carry optional dark-pattern flags from a
   controlled vocabulary, so they can feed a dark-pattern incident registry
   later without changing the format (§8).
6. **Backward-compatible reads.** A new version MUST still accept receipts
   written under earlier `0.x` versions. Writers SHOULD use the newest
   version.

## 3. The receipt

A receipt is a JSON object conforming to `cancel-receipt.schema.json`
(JSON Schema, draft 2020-12). Field summary (new in v0.2 marked ★):

| Field | Required | Meaning |
|---|---|---|
| `format` | yes | Always `"cancel-proof"` |
| `version` | yes | `"0.1"` or `"0.2"` |
| `receipt_id` | yes | `CPR-YYYY-XXXX` — year of creation + 4–12 uppercase letters/digits (§4) |
| `issuer` | yes | `"consumer"` or `"seller"` (see §5 for what each proves) |
| `service.name` | yes | Service name as shown to the consumer |
| `service.domain` | yes | Service domain, e.g. `example.com` |
| `account.type` | yes | `email_partial`, `email_hash`, `account_partial`, `phone_partial`, `username_partial`, or `none` |
| `account.value` | if typed | Partial identifier (`am***@example.com`) or, for `email_hash`, the **salted** SHA-256 hex (§4). Absent when type is `none`. |
| `cancellation.datetime_utc` | yes | When the cancellation was **requested / registered**, ISO 8601 UTC, Zulu form (`2026-11-21T10:32:00Z`) |
| `cancellation.effective_at` ★ | no | When the cancellation **takes effect**, if different (e.g. end of the paid period). A charge between `datetime_utc` and `effective_at` is legitimate. |
| `cancellation.method` | yes | `link`, `button`, `chat`, `phone`, `in_person`, `email`, or `other` |
| `cancellation.reference` | no* | Confirmation/reference number given by the seller |
| `evidence.screenshot_sha256` | no* | Lowercase hex SHA-256 of the screenshot file. The screenshot itself is NOT stored in the receipt. |
| `evidence.screenshot_filename` | no | Original filename, so the holder can find the screenshot again |
| `evidence.items` ★ | no* | Array of `{type, hash?, ref?, received_utc?, source?}` — `type` is `email`, `screenshot`, `pdf`, `reference`, or `response`. Each item needs a `hash` or a `ref`. |
| `signature` ★ | no | Seller signature (§5): `{algorithm: "ES256-JCS", public_key (JWK), signature (base64url), key_url?}` |
| `status` ★ | no | Outcome of the dispute: `no_charge`, `charged_refunded`, `charged_disputed`, or `charged_unresolved` (§4) |
| `dark_pattern_flags` | no | Array from the controlled vocabulary in §8 |
| `charges_after_cancel` | no | Array of `{date, amount?, amount_minor?, currency, note?}` — at least one of `amount` / `amount_minor` (§4) |
| `superseded_by` | no | String (v0.1 form: a receipt id) or object `{receipt_id, type, date?, note?}` (v0.2 form, §4). Readers MUST accept both. |
| `notes` | no | Free text, max 500 characters. No secrets. |
| `created_utc` | yes | When the receipt file was created, ISO 8601 UTC, Zulu form |

\* **At least one of `cancellation.reference`,
`evidence.screenshot_sha256`, or a non-empty `evidence.items` MUST be
present.** A receipt with none of the three is invalid: it is a claim
with no evidence.

## 4. Rules

- **One receipt per cancellation attempt.** A second attempt (e.g. after the
  first was ignored) gets its own receipt with its own ID.
- **No expiry.** A cancellation is a historical fact; a receipt does not
  expire. If the seller later confirms in writing, record the confirmation
  in `superseded_by` — do not delete or rewrite the receipt.
- **Receipts are snapshots; status changes go in a new receipt.** `status`
  records the outcome at the time the receipt was written. If the outcome
  changes (a refund arrives, a dispute opens), write a new receipt and point
  the old one at it with `superseded_by` (`type`: `seller_confirmation`,
  `correction`, or `replacement`).
- **No secrets.** Any receipt containing a password, a full card or account
  number, or a full email address is non-conforming. Publishers SHOULD refuse
  to host such receipts. The check excludes the seller's own reference number
  and the receipt id: a 16-digit confirmation number is not a card number.
- **Salted email hash (v0.2).** For `account.type` = `email_hash`, the value
  MUST be `SHA-256(lowercased email + ":" + receipt_id)`, lowercase hex.
  A bare `SHA-256(email)` is **DEPRECATED**: email addresses are low-entropy
  and a bare hash is reversible with a dictionary attack. The salt ties the
  hash to this receipt, so the same email produces a different hash in every
  receipt and cannot be matched across receipts. The format of the value
  (64 hex characters) is unchanged, so v0.1 receipts with bare hashes still
  validate — but writers MUST NOT produce them, and the reference page does
  not offer the option.
- **Receipt ids.** The year in `receipt_id` MUST be the year of
  `created_utc`. The suffix is 4–12 uppercase letters/digits; new receipts
  SHOULD use **8 characters drawn from a cryptographic random source**
  (not `Math.random`), from the 32-symbol alphabet `A–Z` (without `I`, `O`)
  plus `2–9`. Eight characters give 40 bits of entropy
  (32⁸ ≈ 1.1 × 10¹² ids); the chance of a collision stays below 1% until
  roughly 150,000 receipts. A 4-character suffix (v0.1) remains valid.
- **Dates are UTC.** All datetimes use ISO 8601 with the `Z` suffix.
  `created_utc` MUST NOT be earlier than `cancellation.datetime_utc`.
  `effective_at`, when present, MUST NOT be earlier than
  `cancellation.datetime_utc`; it MAY be in the future (a cancellation
  requested now routinely takes effect at the end of the paid period).
- **The device clock is a claim, not proof.** `datetime_utc` and
  `created_utc` come from the device that wrote the receipt and can be
  wrong or faked. Per-item `received_utc` values in `evidence.items`
  (timestamps from the seller's own messages) are stronger evidence than
  the receipt's own clock. Verifiers SHOULD treat receipt dates as
  "claimed", and treat a seller-signed receipt or a matching seller
  reference as the corroboration.
- **Charges after cancellation** MUST be dated after the **cancellation
  date** (date-only comparison: a same-day charge cannot be proven to be
  after the cancellation time) and use ISO 4217 currency codes (`USD`,
  `EUR`). Amounts SHOULD use `amount_minor` — an integer in the smallest
  currency unit (2999 = $29.99; 3000 = ¥3000) — because decimal floats
  round. `amount` (major units, e.g. 29.99) is kept for v0.1 compatibility
  and MUST have at most 2 decimal places.
- **Supersession is lenient on read, strict on write.** Readers MUST accept
  `superseded_by` as a plain string (v0.1) or as an object (v0.2). Writers
  MUST use the object form.

## 5. Verification

Anyone can verify a receipt without contacting the issuer:

1. **Schema check** — the file validates against
   `cancel-receipt.schema.json` (`validate.py` in this repo, or the Verify
   tab of `index.html`). Errors carry the codes in §6.
2. **Screenshot check** — the holder of the screenshot re-hashes the file
   (SHA-256). If the hash matches `evidence.screenshot_sha256`, the
   screenshot is the one the receipt refers to. A matching hash proves the
   screenshot is unchanged; it does not prove the screenshot is genuine —
   that is a limit of the format, stated honestly.
3. **Signature check** (when `signature` is present) — remove `signature`,
   canonicalize the rest with JCS (RFC 8785), and verify the ECDSA P-256
   signature (`ES256-JCS`: 64-byte raw `r || s`, base64url) against the
   embedded `public_key` (JWK). `validate.py` verifies when the
   `cryptography` package is installed and otherwise reports clearly that
   the signature was NOT verified; the Verify tab of `index.html` verifies
   with WebCrypto. A signature that fails verification makes the receipt
   invalid.

**What each level proves (trust levels):**

| Level | What it is | What it proves |
|---|---|---|
| Consumer self-asserted | `issuer` = `consumer`, no signature | The holder claims a cancellation happened and can point at evidence. It does **not** prove the seller recorded it. |
| Seller unsigned | `issuer` = `seller`, no signature | Whoever published the receipt claims to be the seller. Weak: anyone can write `"seller"` into the field. Treat as a claim, not proof. |
| Seller signed | `issuer` = `seller` + valid `signature` | The holder of the matching private key signed this exact receipt. Trust in the key comes from the key being published at the seller's domain (e.g. `/.well-known/cancel-proof-key.json`, linked as `key_url`) — readers SHOULD compare the embedded key against it. A signature that verifies against an unknown key proves nothing about the seller. |

## 6. Error codes

Validators (`validate.py` and the Verify tab of `index.html`) report the
same codes. Format: `CODE: message`.

| Code | Meaning |
|---|---|
| `E_MISSING_FIELD` | A required field is absent |
| `E_BAD_VALUE` | A field has the wrong type, pattern, or value (including an unexpected extra field) |
| `E_BAD_HASH` | A hash field is not 64 lowercase hex characters |
| `E_NO_EVIDENCE` | No reference number, no screenshot hash, and no non-empty `evidence.items` |
| `E_FUTURE_DATE` | `cancellation.datetime_utc` or `created_utc` is in the future |
| `E_CREATED_BEFORE_CANCEL` | `created_utc` is earlier than `cancellation.datetime_utc` |
| `E_EFFECTIVE_DATE` | `cancellation.effective_at` is earlier than `cancellation.datetime_utc` |
| `E_CHARGE_DATE` | A charge is not dated after the cancellation date |
| `E_RECEIPT_YEAR` | The year in `receipt_id` does not match the year of `created_utc` |
| `E_BAD_CURRENCY` | A currency is not an ISO 4217 code |
| `E_BAD_AMOUNT` | A charge amount is missing, ≤ 0, has more than 2 decimal places, or `amount_minor` is not a positive integer |
| `E_SECRET_DETECTED` | A card-like digit run or a full email address appears in a public field |
| `E_UNKNOWN_FLAG` | A `dark_pattern_flags` entry is not in the vocabulary (§8) |
| `E_BAD_SIGNATURE` | The signature is malformed or does not verify |
| `E_BAD_SUPERSEDED` | `superseded_by` is neither a string nor a well-formed object |
| `E_BAD_STATUS` | `status` is not one of the four values in §3 |
| `E_UNSUPPORTED_VERSION` | `version` is not `"0.1"` or `"0.2"` |

## 7. Worked examples

`examples/v0.1/` holds the two frozen v0.1 receipts (unchanged).
`examples/v0.2/` holds four **fictional, ILLUSTRATIVE** receipts (services
use the reserved `.test` domain; no real company, account, or person):

- `receipt-multi-evidence.json` — one cancellation, three independent
  pieces of evidence (reference + screenshot hash + two evidence items),
  with `effective_at` at the end of the paid period.
- `receipt-salted-hash.json` — account identified by the salted email hash.
- `receipt-seller-signed.json` — a seller-issued receipt with a real
  ES256-JCS signature (the keypair is fictional; the private key was
  discarded after signing).
- `receipt-superseding.json` — the v0.1 wrongful-charge case re-issued as
  v0.2 with `amount_minor` charges and a structured `superseded_by`
  pointing at the seller's written confirmation.

## 8. Dark-pattern flags (controlled vocabulary)

Optional. Each flag names an obstacle the consumer met while cancelling.
The vocabulary is deliberately small; it maps to the EU Digital Fairness
Act proposal (COM(2026) 1100), Annex I, Part III, points 53–62, and to the
vacated FTC rule's §425.6(c)(1) (no live-representative requirement for
online cancellation). **The mapping was checked against the adopted
proposal text** (COM(2026) 1100 final, Annexes, 11 Nov 2026). The flags
are consumer-side labels, not legal classifications — a flag says "this
happened", not "this violates point N".

| Flag | Meaning | DFA anchor |
|---|---|---|
| `hidden_cancel_button` | The cancel control was hidden, buried, or removed | Annex I, point 62 |
| `forced_chat` | Cancellation only possible via live chat | §425.6(c)(1); point 62 |
| `forced_call` | Cancellation only possible by phone | §425.6(c)(1); point 62 |
| `save_offer_wall` | Retention offers blocked or delayed the cancel flow | Annex I, points 56, 62 |
| `confirm_shaming` | The decline option was framed as the wrong choice ("I don't like saving money") | Annex I, point 56 |
| `no_confirmation` | No confirmation, reference, or receipt was given | DFA Art. 23 (acknowledgement) |
| `roach_motel` | Sign-up was easy; cancellation was made hard overall | Annex I, point 62 |

## 9. Registry bridge (phase 2)

Receipts are designed to feed a dark-pattern incident registry without a
format change: a registry entry can cite a receipt by `receipt_id`, group
receipts by `service.domain`, and aggregate `dark_pattern_flags` per
service. The registry itself is a separate project; v0.2 only guarantees
the receipt side of the bridge.

## 10. Limits (stated honestly)

- A receipt proves the holder *claims* a cancellation happened and can
  point at evidence; it cannot prove the seller's systems recorded it.
  Seller-issued receipts (MODEL-RULE-v0.2.md, Art. 2) close that gap —
  and a seller signature closes it only as far as the key is trusted (§5).
- A screenshot hash proves the screenshot is unchanged, not that it is
  genuine. Screenshots can be fabricated; the hash only binds the receipt
  to one specific file.
- Receipt dates come from the writer's device clock and can be wrong or
  faked (§4). A seller reference or a seller signature is the
  corroboration, not the clock.
- The format has no identity system. Anyone can write any name into
  `service.name`. Reputation and abuse handling belong to publishers and
  registries, not to v0.2.

## 11. Versioning

`0.x` versions may change fields. `1.0` will freeze the field set and
guarantee backward-compatible reads. Changes are recorded in the
repository's CHANGELOG. v0.2 accepts v0.1 receipts; v0.1 readers do not
understand v0.2 fields and MUST NOT be used to validate v0.2 receipts.

## Sources

- Restore Online Shoppers' Confidence Act, 15 U.S.C. § 8403 (Pub. L.
  111-345, 29 Dec 2010) — "simple mechanisms … to stop recurring charges".
- FTC Negative Option Rule amendments, 89 FR 90476 (15 Nov 2024), 16 CFR
  § 425.6 — vacated in full, *Custom Communications, Inc. v. FTC*,
  No. 24-3388 (8th Cir. 8 Jul 2025).
- EU Digital Fairness Act proposal, COM(2026) 1100 final (11 Nov 2026),
  Arts. 10, 20–25, Annex I Part III — proposed Regulation, not yet law.
- FTC Negative Option Rule ANPRM, 91 FR 12318 (13 Mar 2026); comments
  closed 13 Apr 2026; no proposed rule yet (as of Sep 2026).
- JSON Canonicalization Scheme (JCS), RFC 8785 (Jun 2020) — canonical
  form signed by `signature`.
- ISO 4217 — currency codes used for `charges_after_cancel[].currency`.
