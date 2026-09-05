# SIH26151 — System Architecture Document

## 1. System Overview

SIH26151 is an evidence-first, analyst-operated Dark-Web Threat Actor Attribution Assistance Platform. It correlates passive technical observations into candidate actor associations using a multi-signal Noisy-OR confidence model (K/I/B/S).

```text
[Source policy + authorization]
       |
       v
[Fixture replay OR authorized Tor collector]
       |
       +--> [Capture status: success / unavailable / blocked / quarantined]
       |
       v
[Immutable raw artifact + SHA-256 + capture metadata]
       |
       v
[Normalizer + safe parser]
       |
       +-------------------+--------------------+-------------------+
       |                   |                    |                   |
       v                   v                    v                   v
[Identity adapter]  [Infra adapter]   [OnionScan adapter]   [Text/behavior adapters]
       |                   |                    |                   |
       +-------------------+--------------------+-------------------+
                               |
                               v
                   [Validated canonical EvidenceUnit store (PostgreSQL)]
                               |
                  +------------+-------------+
                  |                          |
                  v                          v
        [Search projection/index]    [Resolver + fusion]
                                            |
                                            v
                             [Versioned CandidateLink + timeline]
                                            |
                            +---------------+----------------+
                            |                                |
                            v                                v
                   [Graph projection (Neo4j)]     [Case/audit/report store]
                            |                                |
                            +---------------+----------------+
                                            |
                                            v
                  [Streamlit Analyst Dashboard (consumes FastAPI)]
```

## 2. System of Record Rules

| Data Type | Canonical Store | Rebuildable Projection |
|---|---|---|
| Raw capture / scanner artifacts | MinIO / immutable fixture archive | No |
| Capture metadata, source policy, evidence records, links, audit events | PostgreSQL | No |
| Searchable text & entities | PostgreSQL full-text search | Yes |
| Graph nodes & relationships | PostgreSQL link records (primary) / Neo4j (Branch 10 projection) | Yes |
| Exported case reports | Immutable report file + snapshot manifest in PostgreSQL | No |

## 3. Technology Stack & Layering

1. **Presentation Layer:** Streamlit Dashboard (`dashboard.py`) consuming FastAPI REST APIs.
2. **API Layer:** FastAPI server (`api/`) with JWT authentication, RBAC middleware, and rate limiting.
3. **Domain Layer:**
   - Adapters (`adapters/`) mapping observations to canonical `EvidenceUnit` objects.
   - Explainable Fusion (`fusion/`) computing K/I/B/S categories, Noisy-OR scores, and candidate link lifecycle states.
   - Behavior & Stylometry Engines (`analysis/`) extracting behavioral metrics and classical linguistic features.
4. **Data Persistence Layer:**
   - PostgreSQL (Canonical relational database) with a Repository pattern (`db/repositories/`) supporting SQLite dev fallback.
   - MinIO (S3-compatible immutable object storage).
   - Neo4j Community Edition (Graph projection backend for multi-hop Cypher queries).
