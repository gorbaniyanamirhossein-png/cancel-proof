# Changelog

All notable changes to Cancel-Proof. Documents are CC BY 4.0; code is
Apache 2.0.

## 0.2 — 25 November 2026

Format, page, validator, and model rule. Version 0.1 receipts remain
valid: the v0.2 schema accepts `"0.1"` and `"0.2"`. v0.1 files are frozen
unchanged (`CANCEL-PROOF-SPEC-v0.1.md`, `MODEL-RULE-v0.1.md`,
`schemas/cancel-receipt-0.1.schema.json`, `examples/v0.1/`).

### Added

- **Multi-item evidence** (`evidence.items`): a receipt can now carry
  several evidence items — confirmation email, PDF, seller response —
  each with a hash or a reference, a per-item `received_utc`, and a
  `source`. The evidence rule is now: reference OR screenshot hash OR a
  non-empty `evidence.items` list.
- **`cancellation.effective_at`**: when the cancellation takes effect, if
  different from when it was requested (e.g. end of the paid period). A
  charge between request and effective time is legitimate. A future
  `effective_at` is valid.
- **Seller signatures** (`signature`): optional ECDSA P-256 over the JCS
  canonical form (RFC 8785), `ES256-JCS`, with the public key as a JWK and
  an optional `key_url`. The spec defines three trust levels (consumer
  self-asserted, seller unsigned, seller signed) and what each proves.
  The page verifies signatures with WebCrypto; `validate.py` verifies
  when the `cryptography` package is installed and otherwise reports
  clearly that the signature was NOT verified.
- **`status`**: the outcome of the dispute — `no_charge`,
  `charged_refunded`, `charged_disputed`, `charged_unresolved`. A receipt
  is a snapshot; a change of status goes in a superseding receipt.
- **Structured supersession**: `superseded_by` can now be an object
  (`{receipt_id, type, date?, note?}`; types `seller_confirmation`,
  `correction`, `replacement`). The old string form is still accepted on
  read.
- **`amount_minor`**: charge amounts as integers in the smallest currency
  unit (2999 = $29.99). Preferred over `amount`; the page writes it.
- **Error-code catalogue** (spec §6): 17 stable codes (`E_MISSING_FIELD`,
  `E_BAD_HASH`, `E_NO_EVIDENCE`, …) shared by `validate.py` and the
  page's Verify tab.
- **Conformance suite** (`tests/`): 8 valid and 21 invalid fixtures; the
  validator self-test runs them and checks that the jsonschema layer and
  the stdlib fallback layer agree on every fixture (parity check).
- **New examples** (`examples/v0.2/`): multi-evidence, salted-hash,
  seller-signed (real signature; fictional keypair, private key
  discarded), and superseding receipts.

### Changed

- **Salted email hash**: for `account.type` = `email_hash`, the value is
  now `SHA-256(lowercased email + ":" + receipt_id)`. A bare
  `SHA-256(email)` is deprecated — it is reversible with a dictionary
  attack. The value format (64 hex chars) is unchanged, so old receipts
  still validate; the page never offered the option and still does not.
- **Receipt ids**: new receipts use 8 characters from a cryptographic
  random source (`crypto.getRandomValues` on the page). 4-character
  suffixes from v0.1 remain valid.
- **Charge-date rule**: charges must be dated after the **cancellation
  date** (date-only comparison — a same-day charge cannot be proven to be
  after the cancellation time). The spec wording now says what the
  validator enforces.
- **Receipt-id year rule** is now stated in the spec (§4), not only
  enforced by the validator.
- **Currency check**: charges are validated against a real ISO 4217 list
  (validator and page). `BTC`, `USDT` and other non-ISO codes are
  rejected.
- **Page**: multiple charges can be added/removed as rows; export
  (Copy/Download) is blocked while validation errors exist; the
  cancellation-time label now says the input is local time stored as UTC;
  the Verify tab accepts v0.1 and v0.2 receipts and verifies signatures;
  a pure-JS SHA-256 fallback covers browsers without WebCrypto (e.g.
  `file://` pages).
- **Model rule v0.2**: EU consultation deadline corrected to
  **15 January 2027** (verified on the Commission's "Have your say" page,
  initiative 14622); Article 2 now recommends seller signatures with the
  key published under the seller's domain; Article 3 counts a valid seller
  signature as verifying evidence.
- **Dark-pattern flag mapping** (§8 of the spec) was re-checked against
  the adopted DFA proposal text (COM(2026) 1100 final, Annexes,
  11 Nov 2026) and confirmed; the spec now says the flags are
  consumer-side labels, not legal classifications.

### Fixed

- **Secret scan false positive**: a 16-digit seller reference number no
  longer trips the card-number scan (`cancellation.reference` and
  `receipt_id` are excluded).
- **Secret scan gap**: a full email address typed into `notes` or an
  account value is now rejected (`E_SECRET_DETECTED`).
- **Amount floats**: `amount` with more than 2 decimal places is now
  rejected (`E_BAD_AMOUNT`); use `amount_minor`.
- **Fallback validator parity**: the stdlib fallback now covers every
  schema rule, and the self-test compares both validators on the whole
  suite.

### Deferred (not in v0.2)

Public API, translations, regulator-reporting export, dispute-system
integration, statistics, print/PDF export. The dark-pattern registry
remains a separate project.

## 0.1 — 21 November 2026

First public draft: receipt format, JSON Schema, static make/verify
page, validator, two illustrative examples, and a 6-article model
click-to-cancel rule grounded in ROSCA, the vacated FTC rule, and the EU
Digital Fairness Act proposal.
