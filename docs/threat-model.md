# SIH26151 — Security Threat Model

This document describes the threat landscape, attack surface, and mitigations built into the SIH26151 Dark-Web Threat Actor Attribution Platform.

---

## 1. Threat Actors

| Threat Actor | Motivation | Capabilities |
|---|---|---|
| Adversarial dark-web operator | Evade attribution, create false trails | Recycled aliases, style imitation, shared infrastructure, planted decoy indicators |
| Compromised or malicious data source | Poison attribution pipeline with fabricated evidence | Inject forged PGP keys, fake wallet links, spoofed timestamps |
| Insider / unauthorized analyst | Access restricted evidence, tamper with decisions, leak data | Bypass RBAC, delete audit entries, export without authorization |
| Dependency supply-chain attacker | Compromise upstream libraries or scanner binaries | Backdoor OnionScan, inject malicious model weights, modify pip packages |

---

## 2. Attack Surface & Mitigations

### 2.1 Collection Layer
| Attack Vector | Mitigation | Edge Cases |
|---|---|---|
| DNS leak via direct SOCKS5 connection | Enforce `socks5h://` (DNS-over-Tor) in `collection/tor_collector.py` | EC-06 |
| Malicious/oversized response from .onion site | 10 MB response cap, MIME validation, quarantine in `collection/normalizer.py` | EC-03 |
| CAPTCHA/login wall requiring interaction | Passive-only collection; never solve CAPTCHAs, submit forms, or execute JavaScript | EC-04 |
| Source spoofing forged timestamps | Separate `source_claimed_time` vs `captured_at`; `time_confidence` scoring | EC-16 |
| Unauthorized source access | Source allowlist/blocklist in `config/sources.yaml`; kill-switch in `config/source_policy.yaml` | EC-05 |

### 2.2 Analysis & Fusion Layer
| Attack Vector | Mitigation | Edge Cases |
|---|---|---|
| Score inflation via duplicate evidence | Noisy-OR with `independence_group_id` deduplication | EC-24 |
| False positive from shared hosting/CDN/mixer | Indicator role classification (`shared_service_wallet`, `mixer_suspected`), rarity factor, category caps | EC-08, EC-09 |
| Style imitation or LLM-generated posts | Stylometry contribution capped at 0.20; eligibility gates (≥5 posts, ≥1500 chars) | EC-20 |
| Competing attribution hypotheses | Conflict sets with `conflict_set_id`; both candidates displayed to analyst | EC-13 |
| Tier boundary fluctuation | Hysteresis margin of ±0.03 before tier change | EC-25 |

### 2.3 API & Access Layer
| Attack Vector | Mitigation | Edge Cases |
|---|---|---|
| Unauthorized evidence access | 4-tier RBAC (Viewer, Analyst, Reviewer, Admin) with JWT tokens | EC-26 |
| Sensitive data leakage to low-privilege role | `RedactionEngine` masks raw evidence for Viewer role | EC-28 |
| Decision tampering or deletion | Append-only hash-chained audit log (`AuditStore`); integrity verification via `verify_integrity()` | EC-27 |
| Unauthorized export of case data | Export requires Analyst+ role; snapshot freezes exact evidence/model versions | EC-35 |

### 2.4 Infrastructure & Supply Chain
| Attack Vector | Mitigation | Edge Cases |
|---|---|---|
| Compromised OnionScan binary | Pinned binary/container digest; non-root execution; hard timeout (120s); output size limit (5MB) | EC-07, EC-31 |
| Neo4j database compromise or data loss | PostgreSQL is single source of truth; Neo4j is projection-only; reconciliation + rollback engine | EC-32, EC-33 |
| Runtime model download interception | MiniLM weights pre-bundled locally (`models/all-MiniLM-L6-v2/`); zero runtime downloads | EC-37 |
| Secrets committed to repository | `.env` gitignored; `make secret-scan` target; no hardcoded credentials | EC-30 |

---

## 3. Security Design Principles

1. **Defense in Depth:** Multiple independent layers prevent single-point compromise.
2. **Least Privilege:** Collection containers run non-root with restricted network egress. Viewer role cannot access raw evidence.
3. **Immutability:** Audit events are append-only with cryptographic hash chaining. Export snapshots freeze evidence versions.
4. **Fail-Safe Defaults:** Default mode is `fixture_replay` (no live collection). Kill-switch disables all sources instantly.
5. **Transparency:** Every score includes full category breakdown, limitations, and caveats. No black-box decisions.

---

## 4. Residual Risks

| Risk | Severity | Status |
|---|---|---|
| Tor network compromise (global adversary) | High | Out of scope — platform explicitly disclaims Tor defeat |
| Adversarial corpus specifically crafted to fool stylometry | Medium | Mitigated by 0.20 cap; cannot reach high tiers alone |
| Analyst social engineering | Medium | Mitigated by mandatory notes, audit trail, and RBAC separation |
