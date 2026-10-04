# AEGIS synthetic evaluation — 2026-10-05

Small, honest numbers. This is a **synthetic 15-message set**, not a claim
about real-world accuracy. It exists so judges (and we) can see exactly
where the pipeline is conservative and where it isn't.

## Corpus (`eval/corpus.json`, deterministic)

- **7 scam**: the sample PayPal phish + 6 adversarial variants from the
  deterministic red-team engine (homoglyphs, lookalike domains, TLD swaps,
  rephrased threats)
- **8 legit**: hand-written everyday mail — order confirmation, newsletter,
  bank security alert, meeting move, flight itinerary, interview invite,
  utility bill, personal note

Run it yourself: `python scripts/eval.py` (takes ~4 min, live LLM calls).

## Results

| id | expected | predicted | score |
|---|---|---|---|
| scam-paypal-orig | scam | SUSPICIOUS | 0.69 |
| scam-paypal-var02..07 | scam | SUSPICIOUS | 0.69–0.70 |
| legit-order | legit | LIKELY_SAFE | 0.15 |
| legit-newsletter | legit | LIKELY_SAFE | 0.14 |
| legit-bank-alert | legit | LIKELY_SAFE | 0.18 |
| legit-meeting | legit | LIKELY_SAFE | 0.02 |
| legit-flight | legit | LIKELY_SAFE | 0.17 |
| legit-interview | legit | LIKELY_SAFE | 0.05 |
| legit-bill | legit | LIKELY_SAFE | 0.36 |
| legit-personal | legit | LIKELY_SAFE | 0.02 |

- **Scam recall@flagged (SCAM or SUSPICIOUS): 100%** — every scam caught
- **Scam recall@SCAM: 0%**
- **Legit specificity (LIKELY_SAFE): 100%** — zero false positives

## What the 0% means

The eval harness runs the pipeline **without provider enrichment** (no
AgentBoxD phishing score, no vision HTML). In that configuration the
ensemble is conservative by design: forensic scores ~0.97 on every scam,
but the sandbox marks unresolvable domains 0.3 and the weights can't clear
the 0.70 SCAM line — so everything lands SUSPICIOUS at ~0.69.

With the AgentBoxD phishing signal present (the production path), the same
sample scores **0.93 → SCAM**. The SCAM label is effectively reserved for
provider-corroborated cases. That's a calibration choice, not an evasion:
the system would rather say "suspicious, verify" than cry scam — and it
never clears actual scams as safe.

## Reproduce

```bash
python scripts/build_eval_corpus.py  # regenerate the corpus (deterministic)
python scripts/eval.py               # run, writes eval/results.json
```
