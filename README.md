# Cancel-Proof

A shareable, verifiable receipt for a cancelled subscription — proof the
consumer controls, not the seller.

**The problem:** when you cancel a subscription, the proof stays with the
seller. If they keep charging you — or deny you ever cancelled — it's your
word against their database. Cancel-Proof is a small open format for a
cancellation receipt: a JSON file you create at the moment of cancelling, can
publish anywhere, and anyone can verify. No server, no account, no fee.

**Status:** v0.1, draft for public comment (21 November 2026).

## Files

| File | What it is |
|---|---|
| `CANCEL-PROOF-SPEC-v0.1.md` | The format specification |
| `cancel-receipt.schema.json` | JSON Schema (draft 2020-12) |
| `examples/` | Two fictional, ILLUSTRATIVE receipts (clean cancel; wrongful charge) |
| `index.html` | Static page: make a receipt / verify a receipt — runs offline in a phone browser, nothing is uploaded |
| `validate.py` | Validator + self-test (`python3 validate.py --selftest`) |
| `MODEL-RULE-v0.1.md` | Short model click-to-cancel rule, grounded in the real FTC and EU texts |
| `LICENSE.md` | Licences |

## How to use it

1. Open `index.html` in any browser (phone or desktop). No install, no
   internet needed after loading.
2. Fill in the service, when and how you cancelled, and the seller's
   reference number — or attach a screenshot of the confirmation. Only the
   screenshot's SHA-256 hash goes into the receipt; the screenshot itself
   stays on your device.
3. Copy the share text or download the JSON. Post it, attach it to a
   chargeback, send it to a regulator.
4. Anyone can verify it: paste the JSON into the Verify tab, and re-hash
   the screenshot to check it matches.

**Never put secrets in a receipt** — no passwords, no full card or account
numbers, no full email addresses. Receipts are public by design.

## Why now (policy context)

- **EU:** the Digital Fairness Act proposal (COM(2026) 1100, 11 Nov 2026)
  would ban dark patterns and require an easy online termination function —
  but it requires no machine-readable receipt. Public feedback is open on
  the Commission's "Have your say" platform (opened 17 Nov 2026; deadline
  currently listed mid-January 2027 — check the live page). The model rule
  in this repo is written for that consultation.
- **US:** the FTC's 2024 click-to-cancel rule (89 FR 90476) was vacated in
  full on 8 Jul 2025 (*Custom Communications v. FTC*, 8th Cir.) on
  procedural grounds; the FTC's new rulemaking (ANPRM, 91 FR 12318) took
  comments until 13 Apr 2026 and no proposed rule exists yet. ROSCA
  (15 U.S.C. § 8403) still requires "simple mechanisms to stop recurring
  charges" — but gives the consumer no receipt either.

## Roadmap

- **v0.1 (this):** the free layer — format, page, validator, model rule.
- **Phase 2:** a dark-pattern incident registry fed by receipts (receipts
  already carry `dark_pattern_flags` for this).
- **Later, only after proven demand (~10 real requests):** a paid layer —
  one-time dispute-evidence packs. Payments would be direct wallet-to-wallet
  USDT/BTC only; no payment feature exists in v0.1.

## Licences

Documents (spec, model rule, README): **CC BY 4.0**.
Code (validator, page): **Apache 2.0**. See `LICENSE.md`.

*Not legal advice. The model rule is a draft for consultation, not law.*
