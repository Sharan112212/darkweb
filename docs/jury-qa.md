# SIH26151 — Jury Q&A Technical Reference Guide

This document contains pre-formulated, technically precise answers to anticipated questions from the SIH evaluation panel and technical jury.

---

## 1. Core Methodology & Architecture Questions

### Q1: Does your platform deanonymize Tor users or find real-world identities?
> **Answer:** **No.** The platform explicitly does **not** defeat Tor network cryptography, exploit zero-days, or claim real-world identities (e.g., real name or home address). It provides confidence-scored technical associations between dark-web handles, cryptographic identifiers (PGP keys, wallets), and infrastructure endpoints for authorized human analyst review.

### Q2: How do you prevent false positives from shared darknet services like escrow wallets or shared web hosting?
> **Answer:** We enforce **indicator roles** and **category caps**:
> 1. **Indicator Roles:** Wallets associated with known escrows or mixers are tagged as `shared_service_wallet` or `mixer_suspected` and downweighted.
> 2. **Category Caps:** Infrastructure signals (`I`) or text signals (`S`) alone can **never** exceed the `possible_association` tier ($\le 0.65$ or $\le 0.20$ max contribution) without corroborating cryptographic identity (`K` category) or multi-source proof.

### Q3: Why do you use Noisy-OR for score fusion instead of simple averaging or a machine learning classifier?
> **Answer:** Simple averaging dilutes strong evidence when many categories are absent. Machine learning classifiers behave as black boxes that cannot be defended in court. **Noisy-OR** (`P = 1 - \prod(1 - w_i)`):
> 1. Is mathematically sound for combining independent probabilistic evidence.
> 2. Prevents score inflation by deduplicating signals with identical `independence_group_id`.
> 3. Guarantees 100% explainability: every candidate score can be broken down into exact contributing $K, I, B, S$ category weights and limitations.

---

## 2. Technical Implementation & Data Integrity Questions

### Q4: How do you handle air-gapped deployment in high-security environments?
> **Answer:** The platform is **100% air-gap ready**:
> - Sentence-BERT weights (`models/all-MiniLM-L6-v2/`) are bundled locally in the repository.
> - All 16 evaluation test scenarios use local fixture replay (`fixtures/`) with SHA-256 checksum manifests.
> - Python dependencies and Docker images are pre-cached. Zero runtime internet calls are made.

### Q5: How do you ensure chain-of-custody and data integrity for legal investigations?
> **Answer:** We implement three core controls:
> 1. **Capture Provenance:** Every raw artifact is SHA-256 hashed and stored immutably in MinIO or fixture archives alongside HTTP status, capture timestamp, and collection mode.
> 2. **Tamper-Evident Audit Log:** All analyst actions, searches, and decisions are recorded in an append-only audit store backed by cryptographic hash chaining (`prev_hash`).
> 3. **Export Snapshots:** When an analyst exports a case report (PDF/JSON/CSV), the export engine creates an immutable snapshot freezing the exact versions of all evidence, candidate links, and scoring models used at that moment.

### Q6: What happens if your graph database (Neo4j) goes offline or crashes?
> **Answer:** PostgreSQL/SQLite is our single source of truth. Neo4j is purely a graph projection view. If Neo4j goes offline, our `Neo4jProjection` class automatically falls back to an in-memory `NetworkXProjection` without pipeline failure (`EC-07`). Admin endpoints (`/reconcile` and `/rollback`) allow rebuilding the graph projection from canonical records in seconds (`EC-32`).

---

## 3. Data Governance & Security Questions

### Q7: How does Role-Based Access Control (RBAC) protect sensitive data?
> **Answer:** We enforce 4 strict user roles:
> - **Viewer:** Can view profiles, graph topology, and redacted evidence. Raw sensitive content is masked.
> - **Analyst:** Can view full evidence, create cases, add notes, and submit link decisions (`accept`/`reject`/`defer`).
> - **Reviewer:** Can approve or reject case exports and policy changes.
> - **Admin:** Can manage source allowlists, toggle kill-switches, and trigger reconciliation. Admin actions cannot bypass audit logging.

### Q8: How do you handle adversarial style imitation or LLM-generated darknet posts?
> **Answer:** Classical stylometry (`pystylometry`) and MiniLM semantic similarity undergo strict eligibility gates ($\ge 5$ posts, $\ge 1,500$ cleaned characters per persona, language confidence filter). Additionally, text/stylometric evidence is strictly capped at a max contribution of $0.20$, preventing style imitation alone from falsely elevating a pair to high-confidence tiers.
