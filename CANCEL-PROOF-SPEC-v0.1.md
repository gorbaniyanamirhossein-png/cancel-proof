# Cancel-Proof — Shareable Cancellation Receipt Format

**Version:** 0.1 — 21 November 2026
**Status:** Draft for public comment
**Licence:** CC BY 4.0 (this document). Code (validator, page) is Apache 2.0.
**Author:** Amirhossein Gorbaniyan

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
   piece of evidence: the seller's reference number, or the SHA-256 hash of a
   screenshot of the cancellation confirmation (§5).
4. **No infrastructure.** Receipts are plain files. They are created and
   verified in the browser, offline, on a phone.
5. **Registry-ready.** Receipts carry optional dark-pattern flags from a
   controlled vocabulary, so they can feed a dark-pattern incident registry
   later without changing the format (§7).

## 3. The receipt

A receipt is a JSON object conforming to `cancel-receipt.schema.json`
(JSON Schema, draft 2020-12). Field summary:

| Field | Required | Meaning |
|---|---|---|
| `format` | yes | Always `"cancel-proof"` |
| `version` | yes | Format version, `"0.1"` |
| `receipt_id` | yes | `CPR-YYYY-XXXX` — year of creation + 4–12 uppercase letters/digits |
| `issuer` | yes | `"consumer"` (v0.1) or `"seller"` (sellers issuing receipts in this format — see MODEL-RULE-v0.1.md, Art. 2) |
| `service.name` | yes | Service name as shown to the consumer |
| `service.domain` | yes | Service domain, e.g. `example.com` |
| `account.type` | yes | `email_partial`, `email_hash`, `account_partial`, `phone_partial`, `username_partial`, or `none` |
| `account.value` | if typed | Partial identifier (`am***@example.com`) or, for `email_hash`, the lowercase hex SHA-256 of the email. Absent when type is `none`. |
| `cancellation.datetime_utc` | yes | When the cancellation happened, ISO 8601 UTC, Zulu form (`2026-11-21T10:32:00Z`) |
| `cancellation.method` | yes | `link`, `button`, `chat`, `phone`, `in_person`, `email`, or `other` |
| `cancellation.reference` | no* | Confirmation/reference number given by the seller |
| `evidence.screenshot_sha256` | no* | Lowercase hex SHA-256 of the screenshot file. The screenshot itself is NOT stored in the receipt. |
| `evidence.screenshot_filename` | no | Original filename, so the holder can find the screenshot again |
| `dark_pattern_flags` | no | Array from the controlled vocabulary in §7 |
| `charges_after_cancel` | no | Array of `{date, amount, currency, note?}` — charges placed after cancellation |
| `superseded_by` | no | Reference to a seller-issued confirmation that supersedes this receipt, if the seller later confirms in writing |
| `notes` | no | Free text, max 500 characters. No secrets. |
| `created_utc` | yes | When the receipt file was created, ISO 8601 UTC, Zulu form |

\* **At least one of `cancellation.reference` or
`evidence.screenshot_sha256` MUST be present.** A receipt with neither is
invalid: it is a claim with no evidence.

## 4. Rules

- **One receipt per cancellation attempt.** A second attempt (e.g. after the
  first was ignored) gets its own receipt with its own ID.
- **No expiry.** A cancellation is a historical fact; a receipt does not
  expire. If the seller later confirms in writing, record the confirmation in
  `superseded_by` — do not delete or rewrite the receipt.
- **No secrets.** Any receipt containing a password, a full card or account
  number, or a full email address is non-conforming. Publishers SHOULD refuse
  to host such receipts.
- **Dates are UTC.** All datetimes use ISO 8601 with the `Z` suffix.
  `created_utc` MUST NOT be earlier than `cancellation.datetime_utc`.
- **Charges after cancellation** MUST be dated after
  `cancellation.datetime_utc` and use ISO 4217 currency codes (`USD`, `EUR`).

## 5. Verification

Anyone can verify a receipt without contacting the issuer:

1. **Schema check** — the file validates against
   `cancel-receipt.schema.json` (`validate.py` in this repo, or the Verify
   tab of `index.html`).
2. **Screenshot check** — the holder of the screenshot re-hashes the file
   (SHA-256). If the hash matches `evidence.screenshot_sha256`, the
   screenshot is the one the receipt refers to. A matching hash proves the
   screenshot is unchanged; it does not prove the screenshot is genuine —
   that is a limit of the format, stated honestly.

## 6. Worked examples

`examples/` contains two **fictional, ILLUSTRATIVE** receipts (services use
the reserved `.test` domain; no real company, account, or person):

- `receipt-clean-cancel.json` — a clean two-click cancellation.
- `receipt-wrongful-charge.json` — a cancellation followed by two charges,
  with dark-pattern flags, as chargeback evidence.

## 7. Dark-pattern flags (controlled vocabulary)

Optional. Each flag names an obstacle the consumer met while cancelling.
The vocabulary is deliberately small in v0.1; it maps to the EU Digital
Fairness Act proposal (COM(2026) 1100), Annex I, Part III, points 53–62,
and to the vacated FTC rule's §425.6(c)(1) (no live-representative
requirement for online cancellation).

| Flag | Meaning | DFA anchor |
|---|---|---|
| `hidden_cancel_button` | The cancel control was hidden, buried, or removed | Annex I, point 62 |
| `forced_chat` | Cancellation only possible via live chat | §425.6(c)(1); point 62 |
| `forced_call` | Cancellation only possible by phone | §425.6(c)(1); point 62 |
| `save_offer_wall` | Retention offers blocked or delayed the cancel flow | Annex I, points 56, 62 |
| `confirm_shaming` | The decline option was framed as the wrong choice ("I don't like saving money") | Annex I, point 56 |
| `no_confirmation` | No confirmation, reference, or receipt was given | DFA Art. 23 (acknowledgement) |
| `roach_motel` | Sign-up was easy; cancellation was made hard overall | Annex I, point 62 |

## 8. Registry bridge (phase 2)

Receipts are designed to feed a dark-pattern incident registry without a
format change: a registry entry can cite a receipt by `receipt_id`, group
receipts by `service.domain`, and aggregate `dark_pattern_flags` per
service. The registry itself is a separate project; v0.1 only guarantees
the receipt side of the bridge.

## 9. Limits (stated honestly)

- A receipt proves the holder *claims* a cancellation happened and can
  point at evidence; it cannot prove the seller's systems recorded it.
  Seller-issued receipts (MODEL-RULE-v0.1.md, Art. 2) close that gap.
- A screenshot hash proves the screenshot is unchanged, not that it is
  genuine. Screenshots can be fabricated; the hash only binds the receipt
  to one specific file.
- The format has no identity system. Anyone can write any name into
  `service.name`. Reputation and abuse handling belong to publishers and
  registries, not to v0.1.

## 10. Versioning

`0.x` versions may change fields. `1.0` will freeze the field set and
guarantee backward-compatible reads. Changes are recorded in the
repository's CHANGELOG.

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
