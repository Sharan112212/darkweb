# SIH26151 — Baseline Audit Report
## Branch 0 Deliverable

**Audit date:** 2026-09-05
**Auditor:** Dev A (automated + manual inspection)
**Repository:** `e:\darkwebsih\` (promoted from `darklabdoc/darkweb-lab/`)
**Commit baseline:** `af4e454` (master)

> **Audit scope:** Every existing module inspected for: path, entry point, input/output
> format, dependencies, current test data, test coverage, security concerns,
> data-provenance gaps, and the exact adapter required for EvidenceUnit compliance.

---

## Module Inventory

### 1. Tor Scraper / Collector

| Field | Value |
|---|---|
| **File Path** | `scraper/scraper.py` |
| **Entry Point** | `scrape(onion_address)` (called via CLI: `python scraper.py --onion <addr>`) |
| **Language/Runtime** | Python 3.11 |
| **Input Format** | Onion address string; connects via Tor SOCKS5 proxy (`socks5h://127.0.0.1:9050`) |
| **Output Format** | Rows inserted into SQLite `actors` table (handle, category, source, status, last_seen, pgp_fingerprint, wallet_address) and `posts` table (handle, timestamp, text) |
| **Dependencies** | `requests[socks]==2.32.3`, `beautifulsoup4==4.12.3`, `re`, `sqlite3`, `argparse` |
| **Current Test Data** | Live scrape of mock marketplace via Docker Tor hidden service |
| **Test Coverage** | **None** — no unit tests exist |
| **Lines of Code** | 129 lines |

**Security Concerns:**
- No input validation on scraped content (raw HTML parsed without sanitization)
- No MIME type checking before parsing
- No response size limits — unbounded downloads possible
- No timeout configuration — can hang indefinitely
- SOCKS proxy address hardcoded to `127.0.0.1:9050`
- No quarantine path for malformed/binary content
- Database path hardcoded to `scraper/darkweb_intel.db`
- No error handling for network failures — crashes on timeout

**Data-Provenance Gaps:**
- No `capture_id` — scrape events are not recorded
- No SHA-256 hash of raw response
- No `source_url` preservation (only the onion address base)
- No `captured_at` timestamp on the scrape event itself
- No `source_claimed_time` vs observation time distinction
- No status events for failed/offline sources
- No allowlist/blocklist enforcement
- No `independence_group_id` for deduplication
- No `collector_mode` field (no fixture replay support)
- No raw artifact storage — parsed data only

**Adapter Required:** Not a direct adapter — this module needs to be **wrapped** by `collection/capture_manager.py` and `collection/tor_collector.py` which add capture records, hashing, policy checks, and status tracking. The scraper's output then feeds into `adapters/identity_evidence_adapter.py` for PGP/wallet data extracted from profiles.

---

### 2. Infrastructure Matcher

| Field | Value |
|---|---|
| **File Path** | `infra-matcher/match_infra.py` |
| **Entry Point** | CLI: `python match_infra.py --onion <addr>` → calls `get_cert_fingerprint_via_tor()`, `get_cert_fingerprint_clearnet()`, `save_match_to_db()` |
| **Language/Runtime** | Python 3.11 |
| **Input Format** | Onion hostname (via `--onion` arg); clearnet host hardcoded to `nginx-clearnet:8443` |
| **Output Format** | Rows in `infra_links` table (onion_address, clearnet_host, evidence, confidence_score) and `actor_infra_map` (handle, onion_address) |
| **Dependencies** | `argparse`, `socket`, `ssl`, `hashlib`, `sqlite3`, `os`, `socks` (PySocks>=1.7.1) |
| **Current Test Data** | Live TLS handshake with Docker nginx containers sharing `certs/shared_cert.pem` |
| **Test Coverage** | **None** — no unit tests exist |
| **Lines of Code** | 126 lines |

**Security Concerns:**
- Clearnet host hardcoded to `nginx-clearnet:8443` — not configurable
- **Hardcoded confidence score of 98%** — no dynamic assessment of freshness or rarity
- No check for shared hosting / CDN (a shared cert may not indicate same operator)
- Direct TLS connection to clearnet — no proxy enforcement for clearnet checks
- PySocks connection does not use `socks5h://` consistently
- No timeout on TLS handshake
- Actor-to-infra mapping hardcoded for "SecureVault" actors only

**Data-Provenance Gaps:**
- No `capture_id` or `captured_at` on the match event
- No SHA-256 of the raw certificate DER bytes (only the fingerprint)
- No `source_url` — the onion/clearnet endpoints are not recorded as evidence sources
- No freshness factor — a stale certificate match is weighted the same as a fresh one
- No rarity assessment — a cert used by 1000 hosts is weighted the same as a unique one
- No `independence_group_id`
- No `indicator_role` distinction
- No limitations/caveats attached
- No fixture replay mode — requires live TLS connections

**Adapter Required:** `adapters/infra_evidence_adapter.py`
- Must wrap existing `match_infra.py` matching logic
- Emit `EvidenceUnit` with `indicator_type=certificate_fingerprint`, category `I`
- Add freshness factor based on observation recency
- Add rarity caveat when fingerprint is common
- Attach limitation: `"Shared certificate may reflect shared hosting, not operator identity"`
- Replace hardcoded 98% with dynamic `confidence_weight` based on freshness × rarity
- Never allow infrastructure-only evidence to exceed `possible_association` tier

---

### 3. Identity Graph

| Field | Value |
|---|---|
| **File Path** | `identity_graph.py` |
| **Entry Point** | `run_identity_graph()` |
| **Language/Runtime** | Python 3.11 |
| **Input Format** | SQL query on `actors` table — reads `pgp_fingerprint` and `wallet_address` columns |
| **Output Format** | Rows in `relationship_links` table (actor_a, actor_b, link_type='shared_identifier', evidence, confidence_score) |
| **Dependencies** | `sqlite3`, `os`, `itertools.combinations` |
| **Current Test Data** | `personas.json` → 10 actors; `DarkFox`/`DarkFox_v2` share PGP+wallet; `ViperX`/`ViperX_Reborn` share wallet |
| **Test Coverage** | **None** — no unit tests exist |
| **Lines of Code** | 89 lines |

**Security Concerns:**
- **Hardcoded confidence scores**: PGP match = 95%, wallet match = 90%
- No distinction between `key_published` vs `verified_signature` for PGP
- No distinction between personal wallet vs shared/mixer/escrow wallet
- No Unicode normalization or confusable detection on aliases
- Canonical pair ordering `(min(a,b), max(a,b))` is correct

**Data-Provenance Gaps:**
- No `capture_id`, `source_url`, `captured_at`
- No `indicator_role` — all PGP matches treated identically regardless of whether the key was merely published or used to sign content
- No `indicator_role` for wallets — mixer/escrow/shared-service wallets not distinguished
- No `independence_group_id` — shared PGP and shared wallet from same profile could be double-counted
- No `raw_evidence_hash`
- No `time_confidence` or temporal information
- No limitations/caveats attached
- No normalization of PGP fingerprints (no uppercase/space removal/hex validation)
- No wallet chain format validation

**Adapter Required:** `adapters/identity_evidence_adapter.py`
- Wrap existing `run_identity_graph()` logic — do NOT modify the original
- Emit separate `EvidenceUnit` per match type (one for PGP, one for wallet)
- Set `indicator_role`: `key_published` (default) or `verified_signature` (if signature verified)
- Set wallet roles: `wallet_unknown`, `shared_service_wallet`, `mixer_suspected`
- Normalize PGP: uppercase, remove spaces, validate hex length
- Validate wallet: check chain format (BTC/ETH/XMR patterns)
- Detect Unicode confusables on aliases; store original + normalized form
- Assign `independence_group_id` per unique indicator value
- Add limitation for PGP without signature: `"Published key is not proof of key control"`
- Category: `K` (Hard identifiers / cryptographic)

---

### 4. Stylometry (MiniLM Semantic Similarity)

| Field | Value |
|---|---|
| **File Path** | `stylometry.py` |
| **Entry Point** | `run_stylometry()` |
| **Language/Runtime** | Python 3.11 |
| **Input Format** | SQL query on `posts` table — aggregates all post text per `handle` |
| **Output Format** | Rows in `relationship_links` (actor_a, actor_b, link_type='stylometric', evidence, confidence_score where similarity ≥ 0.75) |
| **Dependencies** | `sentence_transformers>=2.2.0`, `torch`, `sqlite3`, `os`, `warnings`, `itertools.combinations` |
| **Current Test Data** | 22 posts across 10 actors; `GhostVendor`/`Nightshade99` designed to match stylistically |
| **Test Coverage** | **None** — no unit tests exist |
| **Lines of Code** | 144 lines |

**Security Concerns:**
- Misleadingly labeled as "stylometry" when it's actually **semantic similarity** (meaning, not style)
- No corpus quality gates: works on any amount of text, even a single word
- No minimum post count requirement (Build Guide requires ≥ 5 posts)
- No minimum character count (Build Guide requires ≥ 1,500 cleaned characters)
- No language detection — silently processes multilingual/translated content
- No template stripping — marketplace boilerplate inflates similarity
- No quote/PGP block/wallet string removal before encoding
- Threshold of 0.75 is hardcoded with no configuration
- Model loads from local `models/all-MiniLM-L6-v2` first, falls back to HuggingFace download
- All post text concatenated into one blob per actor — no structural analysis

**Data-Provenance Gaps:**
- No `capture_id`, `source_url`, `captured_at`
- No `raw_evidence_hash` — no hash of the input corpus
- No corpus metadata (post count, character count, language)
- No `independence_group_id`
- No `model_metadata` (model version, embedding dimensions)
- No `time_confidence`
- No limitations/caveats — cosine similarity presented as "confidence"
- Similarity score × 100 used directly as confidence (0.84 → 84%) — no calibration

**Adapter Required:** `adapters/minilm_evidence_adapter.py`
- Wrap existing `run_stylometry()` — do NOT modify the original
- Label output as `indicator_type=semantic_similarity` (NOT "stylometric" or "authorship")
- Add corpus quality gates: check post count ≥ 5, cleaned chars ≥ 1,500
- Store corpus metadata: `{post_count, char_count, language, corpus_hash}`
- Store model metadata: `{model_name, embedding_dim, similarity_threshold}`
- Assign `independence_group_id` per actor pair
- Add limitation: `"Semantic similarity is supporting evidence only, not authorship proof"`
- Cap contribution per Build Guide §14: text-only cannot exceed `possible_association`
- Category: `S` (Semantic)

---

### 5. Fusion Engine

| Field | Value |
|---|---|
| **File Path** | `fusion.py` |
| **Entry Point** | `run_fusion()` |
| **Language/Runtime** | Python 3.11 |
| **Input Format** | SQL query on `relationship_links` table — reads all edges |
| **Output Format** | Rows upserted into `fused_links` (actor_a, actor_b, fused_confidence, contributing_link_types, signal_count, evidence_summary) |
| **Dependencies** | `sqlite3`, `os`, `math` |
| **Current Test Data** | Output of identity_graph + stylometry modules |
| **Test Coverage** | **None** — no unit tests exist |
| **Lines of Code** | 113 lines |

**Security Concerns:**
- Noisy-OR implementation is mathematically correct
- **No K/I/B/S category classification** — all signals treated uniformly
- No configurable weights — no `config/scoring.yaml`
- No tier mapping (insufficient/unresolved/possible/likely/observed)
- No hysteresis for tier boundary stability
- No conflict set detection
- No explanation generation
- No score capping per category
- Confidence capped at 99% unless an individual signal is 100% — correct safety measure
- Pair ordering `(min(a,b), max(a,b))` is correct

**Data-Provenance Gaps:**
- No `link_version` — no versioning of fused results
- No `score_model_version` or `calculation_input_hash`
- No `state` (proposed/accepted/rejected)
- No `category_breakdown` — just a flat fused score
- No `explanation` or `limitations`
- No `conflict_set_id` or `competing_link_ids`
- No `created_at` / `updated_at` timestamps on versions
- No audit trail for score changes

**Adapter Required:** This module will be **replaced** by `fusion/explainable_fusion.py` in Branch 3. Until then, `adapters/legacy_fusion_adapter.py` bridges new `EvidenceUnit` records back to `relationship_links` format so existing fusion continues working.

---

### 6. Dashboard

| Field | Value |
|---|---|
| **File Path** | `dashboard.py` |
| **Entry Point** | `streamlit run dashboard.py` |
| **Language/Runtime** | Python 3.11, Streamlit ≥ 1.30.0 |
| **Input Format** | Direct SQLite queries on `scraper/darkweb_intel.db` |
| **Output Format** | Web UI with search, actor profiles, linked personas, infrastructure cards, feedback buttons |
| **Dependencies** | `streamlit`, `sqlite3`, `pandas`, `os`, `json`, `datetime`, `feedback_stats` |
| **Current Test Data** | Live database populated by pipeline |
| **Test Coverage** | **None** — no unit tests exist |
| **Lines of Code** | 640 lines |

**Security Concerns:**
- **No RBAC** — all users see everything, including raw PGP/wallet data
- No authentication — anyone with the URL can access
- No redaction controls — sensitive evidence visible to all
- No audit logging — user actions not tracked
- Direct database queries in the UI layer — no API abstraction
- No rate limiting on searches
- SQL queries built with f-strings in some places (potential injection risk)
- CSV/JSON export available to all users — no access control on exports

**Data-Provenance Gaps:**
- No evidence drawer — edges show scores but not the evidence chain
- No graph explorer — no time-bounded, depth-limited graph traversal
- No timeline view
- No case management
- No decision versioning — feedback is binary (confirmed/rejected) with no mandatory reason
- No mandatory disclosure banner
- No export snapshots — exports reflect current mutable state

**Adapter Required:** Dashboard will be **extended** in Branch 5 to consume the FastAPI REST API instead of querying SQLite directly. New components: evidence drawer, graph explorer, RBAC, mandatory disclosure banner.

---

### 7. Feedback Stats

| Field | Value |
|---|---|
| **File Path** | `feedback_stats.py` |
| **Entry Point** | `get_feedback_stats()`, `print_feedback_summary()` |
| **Language/Runtime** | Python 3.11 |
| **Input Format** | SQL query joining `link_feedback` with `relationship_links` |
| **Output Format** | Dict of `{link_type: {confirmed, rejected, total, reliability_pct}}` |
| **Dependencies** | `sqlite3`, `os` |
| **Current Test Data** | Manual feedback entries in `link_feedback` table |
| **Test Coverage** | **None** |
| **Lines of Code** | 88 lines |

**Security Concerns:**
- No RBAC — any user can submit feedback
- No mandatory analyst note — feedback is bare confirmed/rejected
- Feedback is mutable — can be changed without audit trail
- No append-only guarantee

**Data-Provenance Gaps:**
- No decision versioning
- No analyst identity recorded
- No request_id for audit
- No timestamp sequencing guarantee

**Adapter Required:** Will be superseded by `governance/audit.py` (Branch 9) with append-only, tamper-evident audit events including mandatory analyst notes.

---

### 8. Pipeline Runner

| Field | Value |
|---|---|
| **File Path** | `run_pipeline.py` |
| **Entry Point** | `main()` (runs sequentially) |
| **Language/Runtime** | Python 3.11 |
| **Input Format** | None — orchestrates the other modules in sequence |
| **Output Format** | Console output with timing and row counts |
| **Dependencies** | `db_setup`, `identity_graph`, `stylometry`, `fusion`, `sqlite3`, `os`, `sys`, `time` |
| **Current Test Data** | Expects pre-populated `scraper/darkweb_intel.db` |
| **Test Coverage** | **None** |
| **Lines of Code** | 138 lines |

**Security Concerns:**
- No error isolation — if one module crashes, the entire pipeline stops
- No capture step — scraping is a separate manual step
- No adapter pattern — modules write directly to shared database
- Fixed execution order with no configurability

**Data-Provenance Gaps:**
- No pipeline run ID or execution record
- No per-module status tracking
- No rollback capability

**Adapter Required:** Will be extended with capture step, adapter pattern, and error isolation. Each module's failure should be recorded as a status event, not crash the pipeline.

---

### 9. Database Setup

| Field | Value |
|---|---|
| **File Path** | `db_setup.py` |
| **Entry Point** | `setup_schema()` |
| **Language/Runtime** | Python 3.11 |
| **Input Format** | None — creates tables in `scraper/darkweb_intel.db` |
| **Output Format** | SQLite database with 7 tables: actors, posts, relationship_links, infra_links, actor_infra_map, fused_links, link_feedback |
| **Dependencies** | `sqlite3`, `os` |
| **Test Coverage** | **None** |
| **Lines of Code** | 129 lines |

**Security Concerns:**
- SQLite has no user authentication or access control
- No encryption at rest
- No connection pooling (not needed for SQLite, but will be for PostgreSQL)

**Data-Provenance Gaps:**
- No `captures` table
- No `evidence_units` table (canonical EvidenceUnit)
- No `candidate_links` table with versioning
- No `candidate_link_versions` table
- No `audit_events` table (append-only)
- No `timeline_events` table
- No `entities` table (normalized)
- Missing idempotency constraints from App Data Flow §6

**Adapter Required:** Will be replaced/extended by `db/schema.sql` (PostgreSQL) with all required tables, constraints, and idempotency keys. Repository pattern (`db/repository.py`) will abstract PostgreSQL vs SQLite.

---

### 10. Docker Compose

| Field | Value |
|---|---|
| **File Path** | `docker-compose.yml` |
| **Version** | Compose 3.8 |
| **Services** | 4: `nginx-hidden`, `nginx-clearnet`, `marketplace`, `tor` |
| **Networks** | `lab-net` (bridge) |
| **Volumes** | `tor-hidden-data` |

**Security Concerns:**
- **No PostgreSQL service** — needed for canonical data store
- **No MinIO service** — needed for immutable artifact storage
- **No app server container** — needed for FastAPI
- No network egress controls — collector can access any endpoint
- No health checks on any service
- SOCKS proxy exposed on all interfaces (`0.0.0.0:9050`)
- No resource limits (CPU/memory) on any container
- Images not pinned by digest
- No non-root user enforcement

**Missing Services:**
- PostgreSQL (pinned, with health check)
- MinIO (pinned, with health check)
- FastAPI app server
- Neo4j Community Edition (Branch 10)
- OnionScan container (Branch 4, pinned, isolated, non-root)

---

### 11. Mock Marketplace

| Field | Value |
|---|---|
| **File Path** | `marketplace/app.py` + `marketplace/templates/` |
| **Entry Point** | Flask app: `GET /` (directory), `GET /user/<handle>` (profile) |
| **Dependencies** | `flask==3.0.3` |
| **Lines of Code** | 39 lines |

**Status:** Functioning correctly as a synthetic data source. No changes required — this is test infrastructure.

---

### 12. Sample Data

| Field | Value |
|---|---|
| **File Path** | `sample_data/personas.json` (10 actors), `sample_data/posts.json` (22 posts) |

**Current Coverage vs Required 16 Fixtures:**

| # | Required Fixture | Currently Covered? | Gap |
|---|---|---|---|
| 1 | Shared PGP in two profiles | ✅ DarkFox / DarkFox_v2 | — |
| 2 | Text/behavior-only pair → ≤ possible | ✅ GhostVendor / Nightshade99 | No score cap enforcement |
| 3 | GhostVendor → Nightshade99 rebrand | ✅ Partial (no timeline data) | Need temporal migration data |
| 4 | Shared mixer/escrow wallet → negative | ❌ Missing | **Need mixer_pair fixture** |
| 5 | Offline source → 503 → changed | ❌ Missing | Need source transition fixtures |
| 6 | Mirrored/reposted identical page | ❌ Missing | Need mirror fixture |
| 7 | Oversized/malformed HTML | ❌ Missing | Need quarantine fixture |
| 8 | Published PGP vs verified signature | ❌ Missing | Need PGP role distinction fixture |
| 9 | Unicode-confusable/recycled alias | ❌ Missing | Need confusable alias fixture |
| 10 | Competing actor-hypothesis conflict | ❌ Missing | Need conflict set fixture |
| 11 | Translation/code-switching/short corpus | ❌ Missing | Need multilingual fixture |
| 12 | LLM-like/style imitation | ❌ Missing | Need LLM fixture |
| 13 | Stale certificate/header | ❌ Missing | Need stale cert fixture |
| 14 | Concurrent duplicate collection jobs | ❌ Missing | Need idempotency test |
| 15 | Decision/evidence change during export | ❌ Missing | Need export snapshot test |
| 16 | Redaction and unauthorized export | ❌ Missing | Need RBAC test |

**Gap:** Only 3 of 16 required fixtures partially exist. 13 fixtures need to be created in Branch 2+.

---

## Edge Case Gap Analysis

### EC-30: Secrets in Git/Container/Fixture
**Status:** NEEDS VERIFICATION (scan pending)
- `.env` file: Not present (good), `.env.example` being created
- `certs/shared_cert.pem` and `shared_key.pem`: Self-signed test certs — acceptable for lab environment but should not be in production
- No `detect-secrets` or `gitleaks` baseline configured
- No CI secret scanning configured
- **Recommendation:** Add `.env` to `.gitignore` (done), run `detect-secrets` scan, add secret scanning to CI

### EC-37: Air-Gapped Startup
**Status:** PARTIAL PASS
- ✅ MiniLM weights bundled in `models/all-MiniLM-L6-v2/` (model.safetensors 90.8 MB, config.json, tokenizer.json, etc.)
- ✅ `stylometry.py` tries local model first before HuggingFace fallback
- ⚠️ `download_model.py` exists for explicit pre-caching — safe
- ⚠️ Docker images use `nginx:alpine` and `python:3.11-slim` without digest pinning — could fail in air-gapped environment
- ⚠️ `pip install` in Dockerfiles requires internet unless packages are pre-cached
- **Recommendation:** Pin Docker images by digest, bundle pip wheels, verify offline Docker build

### EC-40: Live/Illegal Content
**Status:** NEEDS VERIFICATION (scan pending)
- Sample data uses synthetic names: GhostVendor, Nightshade99, DarkFox, ViperX, etc.
- Marketplace names are synthetic: "SecureVault Market", "Obsidian Forum"
- PGP fingerprints appear synthetic (e.g., `9A3F 21B4 77C0 EE12 5D6A 8F90 11C3 4B22 FA01 9D77`)
- BTC wallet addresses appear synthetic (e.g., `bc1qzp3d8x9k2m4h7j6n5w0e1r2t3y4u5i6o7p8a9`)
- No `.onion` URLs in sample data
- **Recommendation:** Run automated scan for real onion URLs, validate all PGP/wallet data is synthetic

---

## Summary of Gaps by Priority

### Critical (Must fix before any branch proceeds)
1. **Zero test coverage** across all modules — no unit tests, no integration tests
2. **No PostgreSQL** — needed for canonical evidence store
3. **No EvidenceUnit contract** — all modules output ad-hoc formats
4. **13 of 16 required fixtures missing**
5. **No RBAC** — all users have full access

### High (Must fix in early branches)
6. Hardcoded confidence scores in identity_graph (95%/90%) and infra_matcher (98%)
7. No capture/provenance tracking on any data path
8. No evidence versioning or audit trail
9. MiniLM mislabeled as "stylometry" — it's semantic similarity
10. No corpus quality gates on stylometry
11. Dashboard queries database directly — no API layer
12. Docker images not pinned by digest

### Medium (Address in later branches)
13. No timeline view
14. No case management / export snapshots
15. No graph explorer with depth/time limits
16. No conflict set detection
17. No classical stylometry (independent writing-style signal)

---

## Adapter Mapping Summary

| Existing Module | Adapter File | Category | Priority |
|---|---|---|---|
| `identity_graph.py` | `adapters/identity_evidence_adapter.py` | K | Branch 1 |
| `infra-matcher/match_infra.py` | `adapters/infra_evidence_adapter.py` | I | Branch 1 |
| `stylometry.py` | `adapters/minilm_evidence_adapter.py` | S | Branch 1 |
| `fusion.py` | `adapters/legacy_fusion_adapter.py` (bridge) | — | Branch 1 |
| (new) OnionScan | `adapters/onionscan_adapter.py` | I | Branch 4 |
| (new) Behavior engine | `adapters/behavior_adapter.py` | B | Branch 7 |
| (new) Classical stylometry | `adapters/classical_stylometry_adapter.py` | S | Branch 8 |
