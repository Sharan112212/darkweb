# SIH26151 — Edge Case and Risk Register

**Purpose:** Mandatory implementation and test register. A branch cannot be accepted if its applicable P0 edge cases are not tested.

## Priority Definitions
- **P0:** Required for SIH demo and before using any non-fixture input.
- **P1:** Required before a live authorized pilot.
- **P2:** Required for mature operational deployment.

---

## Edge Case Master Table

| ID | Priority | Condition | Required Control | Owning Branch |
|---|---|---|---|---|
| EC-01 | P0 | Source timeout/offline/moved/503 | Status event, retain history, bounded retries | Branch 2 |
| EC-02 | P0 | Mirrors/reposts/duplicate jobs | Content hash + independence group + idempotency | Branch 2 |
| EC-03 | P1 | Malicious/oversized/malformed/binary content | Quarantine, MIME/size/CPU limits, no JS | Branch 2 |
| EC-04 | P0 | Login/CAPTCHA/JS-only/form-based source | Record not-collected reason; never bypass | Branch 2 |
| EC-05 | P1 | Source authorization expires | Approval/expiry/kill switch/blocklist | Branch 9 |
| EC-06 | P1 | Tor proxy loss/direct-egress risk | SOCKS5h-only, direct egress deny, health check | Branch 2 |
| EC-07 | P0 | OnionScan timeout/crash/schema change | Pinned artifact, isolated timeout, fixture fallback | Branch 4 |
| EC-08 | P0 | Shared/stale cert/header/CDN | Rarity/freshness/caveat/cap (I ≤ possible) | Branch 3 / 4 |
| EC-09 | P0 | Mixer/escrow/shared wallet | Wallet role/downweight/cap | Branch 3 |
| EC-10 | P0 | Published/revoked/shared/fake PGP | Verify state/role (published vs signature) | Branch 1 |
| EC-11 | P0 | Recycled/confusable alias | Original+normalized storage, collision warning/cap | Branch 1 / 3 |
| EC-12 | P1 | Planted/deceptive indicator | Independent corroboration + warning flag | Branch 7 |
| EC-13 | P1 | Competing hypotheses | Conflict sets and competing-link UI | Branch 3 / 5 |
| EC-14 | P0 | Wrongly accepted merge | Reversible/versioned memberships | Branch 1 / 3 |
| EC-15 | P0 | Replayed content with dates changed | Dedup score but preserve observation history | Branch 2 |
| EC-16 | P0 | Forged/missing timestamps | Claimed/observed/captured times + confidence | Branch 1 / 6 |
| EC-17 | P1 | Clock skew | UTC/NTP/server event time/sequence | Branch 6 |
| EC-18 | P0 | Topic/template drives similarity | Template stripping + score cap | Branch 7 / 8 |
| EC-19 | P0 | Short/multilingual/translated text | Minimum corpus/language gates | Branch 8 |
| EC-20 | P1 | LLM imitation/style evasion | Support-only label + non-text corroboration | Branch 7 / 8 |
| EC-21 | P0 | Quote/signature/template contamination | Cleaning pipeline/version/corpus hash | Branch 7 / 8 |
| EC-22 | P1 | Model/config version change | Versioned rescore/input hashes | Branch 8 |
| EC-23 | P0 | Missing category evidence misread as zero | Category state labels (not_available vs 0) | Branch 1 / 3 |
| EC-24 | P0 | Duplicate evidence score inflation | Noisy-OR + independence groups | Branch 3 |
| EC-25 | P1 | Tier fluctuates at boundary | Hysteresis (±0.03) + score-change event | Branch 3 |
| EC-26 | P0 | Unauthorized/unexplained decision | RBAC + mandatory reason + audit | Branch 5 / 9 |
| EC-27 | P1 | Audit tampering | Append-only/tamper-evident strategy | Branch 9 |
| EC-28 | P0 | Sensitive evidence leaks | Redaction/access controls/masked logs | Branch 2 / 5 |
| EC-29 | P1 | Bulk insider enumeration | Rate limits/query audit/alerts | Branch 9 |
| EC-30 | P0 | Secret in Git/container/fixture | CI secret scan/env separation | Branch 0 |
| EC-31 | P1 | Compromised dependency | SBOM/lock/digest/vuln scan | Branch 0 / 4 |
| EC-32 | P1 | Graph migration loses data | Adapter/dual-write/reconciliation/rollback | Branch 10 |
| EC-33 | P1 | Search stale/inconsistent | Canonical store first; index reconciliation | Branch 10 |
| EC-34 | P1 | Concurrent processing | Idempotency/unique keys/locking | Branch 2 |
| EC-35 | P0 | Export changes mid-build | Snapshot manifest/version lock | Branch 9 |
| EC-36 | P1 | Retention/takedown/redaction | Retention/legal hold/tombstone policy | Branch 9 |
| EC-37 | P0 | Air-gapped startup/download failure | Bundled artifacts/checksums/no runtime download | Branch 0 / 11 |
| EC-38 | P1 | Graph too large/cyclic/sensitive | Limits/progressive expansion/permission filter | Branch 10 |
| EC-39 | P0 | Empty result misinterpreted | Explicit absence state in UI | Branch 5 / 6 |
| EC-40 | P0 | Demo contains live/illegal content | Synthetic fixture policy/CI scan | Branch 0 / 11 |
