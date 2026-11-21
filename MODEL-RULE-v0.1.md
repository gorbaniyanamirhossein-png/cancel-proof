# Model Click-to-Cancel Rule (with Cancellation Receipt)

**Version:** 0.1 — 21 November 2026
**Status:** MODEL / DRAFT for consultation submission — not law, not legal advice
**Licence:** CC BY 4.0
**Author:** Amirhossein Gorbaniyan

## Preamble: the evidence gap

Every modern cancellation regime requires the same thing — cancelling must be
as easy as signing up — and every one of them leaves the same hole: **the
consumer gets no portable proof that they cancelled.**

- In the United States, ROSCA (15 U.S.C. § 8403) has required "simple
  mechanisms … to stop recurring charges" since 2010, and the FTC's 2024
  Negative Option Rule amendments (89 FR 90476) spelled the duty out in
  detail (§ 425.6: at least as easy as sign-up, same medium, easy to find, no
  live-representative requirement). The amendments were vacated in full on
  procedural grounds on 8 July 2025 (*Custom Communications, Inc. v. FTC*,
  No. 24-3388, 8th Cir.) — the court never reached the merits — and the FTC's
  new rulemaking (ANPRM, 91 FR 12318, 13 Mar 2026; comments closed 13 Apr
  2026) has produced no proposed rule yet. Neither the statute, nor the
  vacated rule, nor the ANPRM gives the consumer a receipt.
- In the European Union, the Digital Fairness Act proposal (COM(2026) 1100,
  11 Nov 2026) requires a labelled termination function (Art. 23) and bans
  ten dark patterns outright (Art. 10; Annex I, Part III, points 53–62) — but
  it requires only an "acknowledgement" within a week, in no specified
  machine-readable form. The seller still holds the only record.

When a seller keeps charging after a cancellation, or denies the cancellation
happened, the dispute is the consumer's word against the seller's database.
Chargebacks, regulator complaints, and press stories fail for one reason: the
consumer controls no evidence.

This model rule closes the gap with one cheap mechanism: **a standard,
machine-readable cancellation receipt** — issued by the seller at the moment
of cancellation, and issuable by the consumer in the same open format when the
seller will not. The format is Cancel-Proof v0.1 (see
`CANCEL-PROOF-SPEC-v0.1.md`); any equivalent open format satisfies the rule.

## Article 1 — Simple cancellation (core duty)

1. A seller offering goods or services with a negative-option feature (an
   offer under which the consumer's silence is treated as acceptance of a
   charge) SHALL provide a simple mechanism for the consumer to cancel the
   feature, avoid being charged, and immediately stop recurring charges.
2. The mechanism MUST be at least as easy to use as the mechanism the
   consumer used to consent, and MUST be provided through the same medium.
3. For cancellation by interactive electronic medium, the mechanism MUST be
   easy to find when the consumer seeks to cancel, and the consumer MUST NOT
   be required to interact with a live or virtual representative if they did
   not do so to consent.
4. For cancellation by telephone, the seller MUST promptly effectuate
   cancellations via a number answered or recording messages during normal
   business hours, at no greater cost than the call used to consent.
5. The steps required to cancel MUST NOT be disproportionately more numerous,
   complex, or time-consuming than is reasonably necessary.

## Article 2 — The cancellation receipt

1. At the moment a cancellation is effected, the seller SHALL issue the
   consumer a cancellation receipt in a machine-readable open format,
   containing at minimum: the seller's name and domain; the date and time of
   cancellation in UTC; a unique confirmation reference; and the method of
   cancellation.
2. The receipt SHALL be delivered on a durable medium and SHALL be
   downloadable by the consumer without further authentication hurdles.
   Issuing it SHALL be free of charge.
3. A receipt conforming to the Cancel-Proof format (v0.1 or later) satisfies
   this Article. Any equivalent open, royalty-free format satisfies it.
4. The seller SHALL retain a copy of each receipt for at least three years
   and SHALL produce it to the competent authority on request.

## Article 3 — Consumer-issued receipts as evidence

1. Where the seller fails to issue a receipt under Article 2, the consumer
   MAY create a receipt in the same open format, recording the same facts.
2. A receipt whose evidence verifies — a seller reference matching the
   seller's records, or a screenshot whose SHA-256 hash matches the hash
   recorded in the receipt — SHOULD be treated by dispute bodies, payment
   networks, and competent authorities as prima facie evidence that the
   cancellation occurred as recorded.
3. Nothing in this Article requires a consumer to publish a receipt.
   Publication is voluntary.

## Article 4 — Banned cancellation dark patterns

In connection with cancellation, the following are unfair in all
circumstances:

1. Hiding, burying, or removing the cancellation control;
2. Requiring the consumer to use live chat or a telephone call to cancel
   when consent was given without one;
3. Presenting retention offers that block or delay the cancellation flow;
4. Framing the option to decline or cancel as the wrong choice
   ("confirm-shaming");
5. Failing to give any confirmation, reference, or receipt for a completed
   cancellation.

## Article 5 — Charges after cancellation

1. A charge placed after a cancellation evidenced by a receipt under
   Article 2 or a verified receipt under Article 3 is presumed unauthorised.
2. On notice from the consumer attaching the receipt, the seller SHALL refund
   the charge within 14 days unless the seller produces evidence that the
   cancellation did not occur.
3. This Article does not affect the consumer's right to seek a chargeback or
   to complain to the competent authority.

## Article 6 — Supervision

1. Competent authorities MAY request anonymised, aggregate statistics on
   cancellations, receipts issued, and charges after cancellation.
2. Receipts published voluntarily by consumers MAY be collected into public
   incident registries for supervisory and research purposes, provided no
   personal data beyond what the consumer chose to publish is added.

## Sources

1. Restore Online Shoppers' Confidence Act, 15 U.S.C. § 8403 (Pub. L.
   111-345, 29 Dec 2010) — full text: uscode.house.gov.
2. FTC, Negative Option Rule amendments, 89 FR 90476 (15 Nov 2024), 16 CFR
   pt. 425 (§§ 425.3–425.6) — adopted 3–2, effective 14 Jan 2025.
3. *Custom Communications, Inc. v. FTC*, No. 24-3388 (8th Cir. 8 Jul 2025)
   — rule vacated in full for failure to prepare a preliminary regulatory
   analysis under § 22 of the FTC Act, 15 U.S.C. § 57b-3(b)(1), after an
   administrative law judge found the rule's impact exceeded $100 million
   per year; the court did not reach the substantive challenges. 1973 rule
   restored: 91 FR 6507 (12 Feb 2026).
4. FTC, Negative Option Rule ANPRM, 91 FR 12318 (13 Mar 2026); comments
   closed 13 Apr 2026; no proposed rule yet (as of Sep 2026).
5. European Commission, Digital Fairness Act proposal, COM(2026) 1100 final
   (11 Nov 2026), procedure 2026/0356 (COD) — Arts. 10, 20–25, 34–35, 38,
   40; Annex I, Part III, points 53–62. Proposed Regulation, not yet law.
6. European Commission, "Making your online experience fairer",
   11 Nov 2026 — commission.europa.eu.

## Where this can go

- **EU:** the Digital Fairness Act proposal is open for public feedback on
  the Commission's "Have your say" platform (opened 17 Nov 2026; deadline
  currently listed mid-January 2027 — 14–15 January reported — and extended
  daily until the proposal is available in all EU languages; check the live
  page). All responses are published and summarised for Parliament and
  Council.
- **US:** the FTC's ANPRM comment period is closed; this text is ready for
  the next comment window, when a proposed rule appears.
