# SIH26151 — Scoring Methodology Document

## 1. Multi-Category Confidence Model (K / I / B / S)

The platform evaluates technical evidence across four distinct signal categories:

1. **Category K — Cryptographic & Hard Identifiers:** PGP key fingerprints, cryptocurrency wallet addresses, cryptographic signatures, verified handles. Max contribution: 1.00 (uncapped).
2. **Category I — Infrastructure:** SSL certificate fingerprints, co-located services, server headers, OnionScan findings. Max contribution: 0.65 (capped at `possible_association` unless corroborated).
3. **Category B — Behavioral:** Posting-time UTC patterns, vocabulary overlap, structural template hashes. Max contribution: 0.65 (capped at `possible_association` unless corroborated).
4. **Category S — Semantic & Stylometric:** Sentence-BERT semantic similarity, classical linguistic features (function words, n-grams). Max contribution: 0.20 (capped per Build Guide §14).

## 2. Noisy-OR Probabilistic Formula

Within each category and across categories, independent evidence is fused using the Noisy-OR formula:

\[ P_{\text{fused}} = 1 - \prod_{i=1}^{n} (1 - w_i) \]

Where \(w_i\) is the calibrated confidence weight of each unique `independence_group_id`. Duplicate observations sharing the same `independence_group_id` take the maximum confidence weight without inflating the score.

## 3. Tier Mapping & Boundary Hysteresis

| Fused Score Range | Tier Name |
|---|---|
| 0.00 – 0.19 | `insufficient_evidence` |
| 0.20 – 0.39 | `unresolved` |
| 0.40 – 0.69 | `possible_association` |
| 0.70 – 0.89 | `likely_same_actor` |
| 0.90 – 1.00 | `observed_technical_identity` |

### Hysteresis Margin (±0.03) (EC-25)
Near tier boundaries, if a new calculation's score is within ±0.03 of the previous calculation's score, the system retains the previous tier string to eliminate boundary flicker.

## 4. Conflict Resolution & Competing Hypotheses

When an entity is associated with multiple competing entities via conflicting cryptographic keys, the system groups them into a `conflict_set_id` and registers `competing_link_ids` for analyst review.
