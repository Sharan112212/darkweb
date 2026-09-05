# SIH26151 — Evidence-First Dark-Web Threat Actor Attribution Platform

An evidence-first intelligence correlation and attribution platform designed to link dark-web actor personas, cryptographic identifiers, infrastructure endpoints, and linguistic footprints into confidence-scored candidate associations. Built on PostgreSQL as the canonical system of record, the platform enforces strict data provenance, Noisy-OR probabilistic fusion, role-based access controls (RBAC), tamper-evident audit logging, and offline air-gapped evaluation.

> **Mandatory System Disclosure Statement**  
> *"This system provides confidence-scored technical associations for authorized analyst review. It does not defeat Tor, establish a person's real-world identity, or replace legal/forensic investigation."*

---

## Core Capabilities & Features

- **Canonical Data Provenance & Ingestion (`models/evidence.py` & `collection/`)**
  - Standardized `EvidenceUnit` contract tracking source URL, claimed timestamp, captured timestamp, raw content SHA-256 hash, extraction confidence, and source reliability.
  - SOCKS5h Tor proxy collector with passive-only collection controls (no JavaScript execution, form submission, or CAPTCHA bypass).
  - Fixture replay engine (`collection/fixture_replayer.py`) supporting offline testing and source transition states (online $\rightarrow$ 503 offline $\rightarrow$ content changed).
  - Automatic quarantine path for malformed, oversized (>10MB), or binary responses (`collection/normalizer.py`).

- **Multi-Category Explainable Fusion (`fusion/`)**
  - Probabilistic Noisy-OR engine ($P = 1 - \prod(1 - w_i)$) deduplicated by `independence_group_id`.
  - Evidence categorization into **K** (Cryptographic & Hard Identifiers), **I** (Infrastructure), **B** (Behavioral), and **S** (Semantic & Stylometric).
  - Enforced evidence caps: text/stylometric signals alone capped at `possible_association` ($\le 0.20$ max contribution); lone infrastructure or behavioral signals capped at $\le 0.65$.
  - Tier mapping with hysteresis ($\pm 0.03$ boundary margin) across 5 association tiers: `insufficient_evidence`, `unresolved`, `possible_association`, `likely_same_actor`, and `observed_technical_identity`.
  - Conflict sets (`fusion/conflict_resolver.py`) linking competing attribution hypotheses under a shared `conflict_set_id`.

- **OnionScan Infrastructure Correlation (`scanners/` & `adapters/onionscan_adapter.py`)**
  - Subprocess wrapper for `onionscan` executing in isolated, non-root environments with 120-second hard timeouts and 5MB output caps.
  - Maps open directories, server status leaks, SSH host keys, TLS certificates, and analytics IDs to Category **I** evidence with freshness decay and shared-hosting caveats.

- **Linguistic & Behavioral Analysis (`analysis/`)**
  - **MiniLM Semantic Similarity (`adapters/minilm_evidence_adapter.py`):** Pre-cached SentenceTransformer cosine similarity with post/character count eligibility gates.
  - **Classical Stylometry (`analysis/classical_stylometry.py`):** Multi-feature extraction (50+ function-word frequencies, sentence-length distribution, punctuation habits, character 3–5 n-grams) with PGP/wallet/URL regex cleaning pipelines.
  - **Behavioral Engine (`analysis/behavior_engine.py`):** 24-hour diurnal posting histograms, vocabulary Jaccard overlap, post template hashing, and persona migration detection.

- **Graph Explorer & Reconciliation (`graph/`)**
  - Cypher-based `Neo4jProjection` with automatic, graceful fallback to in-memory `NetworkXProjection` when Neo4j is offline (`EC-07`).
  - Subgraph extraction (`get_subgraph()`) with date range filtering (`from`/`to`), hop depth cutoffs (1–5), and 100-node truncation caps (`truncated: true`) (`EC-38`).
  - `GraphReconciliationEngine` providing canonical store backfill, 1:1 entity/link count validation, and zero-data-loss projection rollback (`EC-32`).

- **Governance, Audit & Snapshot Exports (`governance/`, `cases/`, `export/`)**
  - **RBAC Enforcement (`api/rbac.py`):** 4 roles — `Viewer` (redacted content), `Analyst` (full evidence, decisions, cases), `Reviewer` (approval), and `Admin` (source policy, kill-switch, reconciliation).
  - **Tamper-Evident Audit Store (`governance/audit.py`):** Append-only audit log with cryptographic SHA-256 hash chaining (`prev_hash`) and programmatic verification (`verify_integrity()`).
  - **Snapshot Exporter (`export/exporter.py`):** Freezes exact versions of evidence, links, and scoring models prior to rendering JSON, CSV, or PDF case reports.

---

## Tech Stack & Architecture

- **Runtime & Language:** Python 3.11 / 3.14
- **REST API Framework:** FastAPI 0.100+ / Uvicorn (ASGI)
- **UI Dashboard:** Streamlit 1.30+ / Pandas / Pyvis
- **Canonical Storage:** PostgreSQL 16 (production) with SQLite 3 fallback (`db/connection.py`)
- **Object Storage:** MinIO (raw artifact storage) / Local Fixture Archive
- **Graph Engines:** Neo4j 5.x (Cypher projection) / NetworkX 3.0 (in-memory fallback)
- **Machine Learning & NLP:** `sentence-transformers` (`all-MiniLM-L6-v2`), `scikit-learn`, `pystylometry`
- **Security & Utilities:** PyJWT (Authentication), ReportLab (PDF export), PyYAML, PySocks

### Directory Structure

```text
e:\darkwebsih\
├── api/                                # FastAPI REST API application & RBAC middleware
│   ├── app.py                          # Application factory, CORS, and route registration
│   ├── audit_middleware.py             # Automatic request logging & audit chain middleware
│   ├── rbac.py                         # JWT token creation and role-based access dependencies
│   └── routes/                         # REST API route handlers
│       ├── actors.py                   # GET /api/v1/actors/{actor_id}[/graph]
│       ├── admin.py                    # GET/POST /api/v1/admin/sources, kill-switch
│       ├── audit.py                    # GET /api/v1/audit
│       ├── auth.py                     # POST /api/v1/auth/token
│       ├── captures.py                 # GET /api/v1/captures
│       ├── cases.py                    # POST /api/v1/cases, GET /api/v1/cases/{case_id}
│       ├── entities.py                 # GET /api/v1/entities/{type}/{id}
│       ├── evidence.py                 # GET /api/v1/evidence/{evidence_id}
│       ├── exports.py                  # POST /api/v1/exports, GET /api/v1/exports/{export_id}
│       ├── graph.py                    # GET /api/v1/graph/projection, POST /paths, /reconcile, /rollback
│       ├── health.py                   # GET /api/v1/health
│       ├── links.py                    # GET /api/v1/links/{link_id}, POST /decision
│       ├── search.py                   # POST /api/v1/search
│       └── timeline.py                 # GET /api/v1/actors/{actor_id}/timeline
├── adapters/                           # Data mapping adapters converting inputs to EvidenceUnits
│   ├── base_adapter.py                 # Abstract adapter interface
│   ├── behavior_adapter.py             # Maps diurnal/vocabulary metrics to Category B
│   ├── classical_stylometry_adapter.py # Maps stylometric feature vectors to Category S
│   ├── identity_evidence_adapter.py    # Maps PGP/wallet indicators to Category K
│   ├── infra_evidence_adapter.py       # Maps TLS certs/infra matches to Category I
│   ├── minilm_evidence_adapter.py      # Maps MiniLM cosine similarity to Category S
│   └── onionscan_adapter.py            # Maps OnionScan findings to Category I
├── analysis/                           # Analytics engines
│   ├── behavior_engine.py              # Posting schedule, vocab overlap & persona migration
│   └── classical_stylometry.py         # Function words, sentence length & n-grams feature extractor
├── cases/                              # Case management subsystem
│   └── case_manager.py                 # Case creation, entity referencing, and note tracking
├── collection/                         # Data acquisition & provenance framework
│   ├── capture_manager.py              # Capture record creation, SHA-256 hashing, MinIO upload
│   ├── fixture_replayer.py             # Default mode: replay from local HTML fixtures
│   ├── normalizer.py                   # MIME validation, size caps (>10MB), quarantine path
│   └── tor_collector.py                # SOCKS5h Tor proxy client with passive controls
├── config/                             # Declarative platform configurations
│   ├── scoring.yaml                    # Category weights, max caps, tiers, hysteresis margin
│   ├── source_policy.yaml              # Collection mode, timeouts, request delays, MIME allowlist
│   └── sources.yaml                    # Source allowlist and blocklist definitions
├── db/                                 # Storage layer & repository pattern
│   ├── connection.py                   # Unified connection manager (PostgreSQL + SQLite fallback)
│   ├── schema.sql                      # DDL schema for captures, evidence, links, audit, entities
│   ├── migrations/                     # Database migrations package
│   │   └── 001_initial_schema.py       # Initial DDL migration script
│   └── repositories/                   # Data access repositories
│       ├── audit_repo.py               # Append-only audit store persistence
│       ├── capture_repo.py             # Capture record persistence
│       ├── case_repo.py                # Case reference persistence
│       ├── entity_repo.py              # Entity records persistence
│       ├── evidence_repo.py            # EvidenceUnit persistence & idempotency
│       ├── export_repo.py              # Case export snapshot persistence
│       ├── link_repo.py                # CandidateLink persistence & versioning
│       └── timeline_repo.py            # Timeline event persistence
├── docs/                               # Project documentation & deliverables
│   ├── APP_DATA_FLOW_FINAL.md          # System data flow specification
│   ├── PRD_FINAL.md                    # Product requirements document
│   ├── analyst-guide.md                # Analyst user manual
│   ├── architecture.md                 # System architecture overview
│   ├── baseline-audit.md               # Baseline audit log
│   ├── data-contracts.md               # Pydantic data contract schemas
│   ├── data-governance.md              # Data governance & retention policies
│   ├── deliverables/                   # Official project PDFs
│   ├── demo-script.md                  # 5-minute live jury presentation script
│   ├── jury-qa.md                      # Technical jury Q&A reference guide
│   ├── runbook-local-demo.md           # Offline air-gapped demo runbook
│   ├── scoring-methodology.md          # Probabilistic Noisy-OR fusion specification
│   ├── test-plan.md                    # 3-tier test strategy & fixture mapping
│   └── threat-model.md                 # Threat model & attack surface mitigations
├── export/                             # Reporting & snapshot engine
│   └── exporter.py                     # Freezes evidence snapshots; renders JSON, CSV, PDF reports
├── fixtures/                           # Offline test fixture library (16 test scenarios)
│   ├── archive/                        # Hash-addressed fixture storage
│   ├── blocked/                        # CAPTCHA/login test pages
│   ├── manifests/                      # SHA-256 fixture checksum manifest
│   ├── market-a/                       # Mock marketplace profiles & posts
│   ├── market-b/                       # Reposts, mirrors & oversized HTML fixtures
│   ├── onionscan/                      # Synthetic scanner JSON outputs
│   └── stylometry/                     # Calibration corpus pairs
├── fusion/                             # Probabilistic explainable fusion engine
│   ├── category_classifier.py          # Classifies indicators into K, I, B, S
│   ├── conflict_resolver.py            # Competing hypothesis detection & conflict set grouping
│   ├── explainable_fusion.py           # Noisy-OR fusion, score caps, tier mapping, hysteresis
│   ├── explanation_builder.py          # Deterministic analyst explanation string builder
│   └── link_lifecycle.py               # CandidateLink state machine (proposed -> accepted/rejected)
├── governance/                         # Compliance & audit security
│   ├── audit.py                        # Cryptographic SHA-256 hash-chained audit store
│   ├── redaction.py                    # Role-based evidence field masking engine
│   └── retention.py                    # Legal hold & tombstone retention policy manager
├── graph/                              # Network graph projection subsystem
│   ├── base_graph.py                   # Abstract BaseGraphProjection interface
│   ├── neo4j_projection.py             # Neo4j Cypher projection with NetworkX fallback
│   ├── networkx_projection.py          # In-memory graph projection, ego subgraph & truncation
│   ├── path_finder.py                  # Multi-hop attribution path analysis
│   └── reconciliation.py               # Canonical database backfill, count check & rollback
├── models/                             # Pydantic domain models & cached AI assets
│   ├── all-MiniLM-L6-v2/               # Pre-cached SBERT model weights (offline air-gap)
│   ├── audit.py                        # AuditEvent & TimelineEvent schemas
│   ├── candidate_link.py               # CandidateLink & CategoryScore schemas
│   ├── capture.py                      # Capture record schema
│   ├── enums.py                        # Standard string enums (Tiers, IndicatorTypes, Roles)
│   └── evidence.py                     # EvidenceUnit canonical schema
├── scanners/                           # Scanner integration wrappers
│   ├── base_scanner.py                 # Abstract scanner interface
│   ├── onionscan_parser.py             # Known field extractor for OnionScan JSON
│   └── onionscan_runner.py             # Subprocess executor with timeout & output caps
├── timeline/                           # Timeline correlation
│   └── event_builder.py                # Chronological event builder with time confidence
├── tests/                              # Comprehensive test suite (238 automated tests)
│   ├── api/                            # REST API & RBAC integration tests
│   ├── fixtures/                       # Fixture transition & dedup tests
│   ├── integration/                    # End-to-end branch pipeline tests (Branches 0–11)
│   └── unit/                           # Unit tests for models, fusion, stylometry, graph, audit
├── dashboard.py                        # Streamlit web dashboard interface
├── docker-compose.yml                  # Docker orchestration (PostgreSQL, MinIO, Nginx, Tor)
├── Makefile                            # Command automation targets
├── requirements.txt                    # Consolidated Python dependencies
└── run_pipeline.py                     # Batch pipeline execution runner
```

---

## Prerequisites & Installation

### System Prerequisites
- **Python:** Version `3.11` or higher
- **Docker & Docker Compose:** Required for running PostgreSQL, MinIO, Nginx, and Tor containers.
- **Git:** For source code management.

### Environment Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Sharan112212/darkweb.git
   cd darkweb
   ```

2. **Create and Activate a Virtual Environment:**
   ```bash
   # On Linux/macOS:
   python -m venv venv
   source venv/bin/activate

   # On Windows (PowerShell):
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## Environment Configuration

Copy the template file `.env.example` to create your local `.env` file:
```bash
cp .env.example .env
```

| Variable | Description | Default Value | Mandatory? |
|---|---|---|---|
| `POSTGRES_HOST` | PostgreSQL server hostname | `localhost` | No (falls back to SQLite if unreachable) |
| `POSTGRES_PORT` | PostgreSQL server port | `5432` | No |
| `POSTGRES_DB` | Database name | `darkweb_intel` | No |
| `POSTGRES_USER` | Database user | `darkweb` | No |
| `POSTGRES_PASSWORD` | Database password | `changeme_in_production` | No |
| `MINIO_ENDPOINT` | MinIO object storage endpoint | `localhost:9000` | No (falls back to local filesystem) |
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` | No |
| `MINIO_SECRET_KEY` | MinIO secret key | `changeme_in_production` | No |
| `MINIO_BUCKET` | MinIO bucket name for raw artifacts | `raw-artifacts` | No |
| `COLLECTOR_MODE` | Ingestion mode (`fixture_replay`, `authorized_tor`, `authorized_clearnet`) | `fixture_replay` | Yes |
| `TOR_SOCKS_PROXY` | SOCKS5h Tor proxy URI for isolated egress | `socks5h://127.0.0.1:9050` | No |
| `NEO4J_URI` | Neo4j Bolt connection URI | `bolt://localhost:7687` | No (falls back to NetworkX if offline) |
| `NEO4J_USER` | Neo4j username | `neo4j` | No |
| `NEO4J_PASSWORD` | Neo4j password | `changeme_in_production` | No |

---

## Database Initialization & Migrations

The platform utilizes a Repository Pattern (`db/repositories/`) allowing seamless execution against **PostgreSQL** or a local **SQLite** database.

### Initializing the Schema

To create all canonical tables (`captures`, `evidence_units`, `candidate_links`, `candidate_link_versions`, `audit_events`, `timeline_events`, `entities`, `cases`, `exports`) and apply idempotency constraints:

```bash
# Execute initial DDL migration script:
python db/migrations/001_initial_schema.py
```

### Full Demo Environment Reset
To re-initialize the database schema and populate seed data:
```bash
make demo-reset
```
*Behind the scenes, this executes `python db_setup.py` followed by `python run_pipeline.py`.*

---

## Running the Application & Usage

### 1. Starting the Stack via Docker Compose
To launch PostgreSQL, MinIO, Nginx hidden/clearnet twins, and Tor containers:
```bash
make up
```
To shut down containers and remove volumes:
```bash
make down
```

### 2. Launching the Backend API Server
Start the FastAPI REST server:
```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation will be accessible at: `http://localhost:8000/docs`

### 3. Launching the Web Dashboard
Start the Streamlit analyst interface:
```bash
streamlit run dashboard.py --server.port 8501
```
Open `http://localhost:8501` in your browser.

---

### Practical API Usage Examples

#### Generate JWT Authentication Token
```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=analyst_bob&role=analyst"
```

#### Fetch Actor Profile (Analyst Role)
```bash
curl -X GET "http://localhost:8000/api/v1/actors/GhostVendor" \
     -H "Authorization: Bearer <YOUR_JWT_TOKEN>"
```

*Sample Response Snippet:*
```json
{
  "actor_id": "GhostVendor",
  "found": true,
  "entity": {
    "entity_id": "GhostVendor",
    "entity_type": "Persona",
    "canonical_name": "GhostVendor"
  },
  "links": [
    {
      "link_id": "link_gv_ns99",
      "other_entity": "Nightshade99",
      "tier": "likely_same_actor",
      "score": 0.82,
      "state": "proposed",
      "score_status": "observed",
      "category_breakdown": { "K": 0.0, "I": 0.0, "B": 0.78, "S": 0.20 },
      "limitations": ["Text & Stylometry signals alone capped at possible_association tier unless corroborated"],
      "explanation": "Association based on behavioral posting pattern overlap and stylometric similarity."
    }
  ],
  "link_count": 1,
  "evidence_count": 4,
  "disclosure": "This system provides confidence-scored technical associations for authorized analyst review. It does not defeat Tor, establish a person's real-world identity, or replace legal/forensic investigation."
}
```

#### Query Ego Subgraph with Date Bounds and Limits
```bash
curl -X GET "http://localhost:8000/api/v1/actors/GhostVendor/graph?depth=2&min_score=0.40&limit=50" \
     -H "Authorization: Bearer <YOUR_JWT_TOKEN>"
```

#### Search Attribution Paths Between Two Entities
```bash
curl -X POST "http://localhost:8000/api/v1/graph/paths" \
     -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "source_entity_id": "GhostVendor",
       "target_entity_id": "Nightshade99",
       "max_hops": 3,
       "min_score": 0.20
     }'
```

#### Trigger Admin Projection Reconciliation
```bash
curl -X POST "http://localhost:8000/api/v1/graph/reconcile" \
     -H "Authorization: Bearer <ADMIN_JWT_TOKEN>"
```

---

## Testing & Verification

The platform maintains an automated test suite comprising **238 unit and integration tests** covering schema validation, adapters, Noisy-OR fusion, score caps, OnionScan parsing, stylometry gates, RBAC, tamper-evident audit logs, case exports, and graph reconciliation.

### Run All Unit and Integration Tests
```bash
make test
```
*Or directly via pytest:*
```bash
python -m pytest tests/ -v --tb=short
```

### Run Code Formatting and Security Scans
```bash
make lint
```
*Runs `flake8` for syntax compliance and `bandit` for security vulnerability scanning.*

### Run Secret Detection Audit
```bash
make secret-scan
```

---

## License & Contribution

### License
This project is developed for the **Smart India Hackathon (SIH) Problem Statement 26151**. Refer to the primary project documentation for licensing terms.

### Contribution Guidelines
1. All changes must be developed on feature branches (`feat/branch-<n>-<name>`).
2. Maintain strict data provenance — every new evidence source must pass through an `EvidenceUnit` adapter.
3. Every pull request must pass `make test` and `make lint` without regressions before merging into `develop`.
