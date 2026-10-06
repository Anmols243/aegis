# AEGIS v2 evaluation (real models, live API)

Run: 2026-10-06 02:45 UTC. Synthetic set: a pipeline sanity check, not a real-world accuracy claim.

| Metric | Value |
|---|---|
| n | 22 |
| scams | 12 |
| legit | 10 |
| scam_recall_flagged | 1.0 |
| scam_recall_at_SCAM | 1.0 |
| legit_cleared | 1.0 |
| precision_flagged | 1.0 |
| latency_mean_s | 15.1 |
| latency_p50_s | 14.35 |
| latency_max_s | 31.88 |
| runs_with_failed_stage | 1 |

| Case | Set | Expected | Verdict | Score | Time (s) |
|---|---|---|---|---|---|
| scam-paypal-orig | corpus | SCAM | SCAM | 0.72 | 20.21 |
| scam-paypal-var02 | corpus | SCAM | SCAM | 0.725 | 19.52 |
| scam-paypal-var03 | corpus | SCAM | SCAM | 0.72 | 14.35 |
| scam-paypal-var04 | corpus | SCAM | SCAM | 0.737 | 18.93 |
| scam-paypal-var05 | corpus | SCAM | SCAM | 0.732 | 21.38 |
| scam-paypal-var06 | corpus | SCAM | SCAM | 0.737 | 20.06 |
| scam-paypal-var07 | corpus | SCAM | SCAM | 0.72 | 10.2 |
| legit-order | corpus | LIKELY_SAFE | LIKELY_SAFE | 0.089 | 6.18 |
| legit-newsletter | corpus | LIKELY_SAFE | LIKELY_SAFE | 0.079 | 5.39 |
| legit-bank-alert | corpus | LIKELY_SAFE | LIKELY_SAFE | 0.089 | 6.35 |
| legit-meeting | corpus | LIKELY_SAFE | LIKELY_SAFE | 0.013 | 9.74 |
| legit-flight | corpus | LIKELY_SAFE | LIKELY_SAFE | 0.089 | 13.67 |
| legit-interview | corpus | LIKELY_SAFE | LIKELY_SAFE | 0.032 | 13.59 |
| legit-bill | corpus | LIKELY_SAFE | LIKELY_SAFE | 0.089 | 17.56 |
| legit-personal | corpus | LIKELY_SAFE | LIKELY_SAFE | 0.013 | 6.7 |
| paypal-phish | samples | SCAM | SCAM | 0.836 | 8.16 |
| ceo-gift-cards | samples | SCAM | SCAM | 0.947 | 11.38 |
| parcel-fee | samples | SCAM | SCAM | 0.762 | 31.88 |
| injection-phish | samples | SCAM | SCAM | 0.794 | 22.55 |
| html-display-mismatch | samples | SCAM | SCAM | 0.818 | 11.54 |
| legit-receipt | samples | LIKELY_SAFE | LIKELY_SAFE | 0.019 | 25.09 |
| legit-personal | samples | LIKELY_SAFE | LIKELY_SAFE | 0.013 | 17.44 |
