# SIH26151 — Final App Flow and Data Flow Specification

**Companion to:** `SIH26151_final_build_guide.PDF`

## 1. Route Map

```text
/login
/search
/entities/:entityType/:entityId
/evidence/:evidenceId
/actors/:actorId
/actors/:actorId/graph
/actors/:actorId/timeline
/links/:linkId
/cases
/cases/:caseId
/exports/:exportId
/admin/sources
/admin/audit
```

## 2. User Flow Detail

### Search to Evidence
```text
User submits query
 -> API validates query + role + rate limit
 -> canonical entity/evidence query executes
 -> search projection enriches result where available
 -> API returns redacted result, evidence availability and explanation state
 -> user opens entity/evidence
```
*If there are no results, the UI must state one of:* `no matching evidence collected`, `source unavailable`, `search restricted by role`, `data exists but is redacted`, or `no association found`. Never imply an unsearched source is negative evidence.

### Entity to Candidate Actor
```text
Entity detail
 -> load observations and related CandidateLinks
 -> show original and normalized forms
 -> show source/capture/observation dates
 -> open a candidate actor profile only when association state permits
```

### Candidate Actor to Decision
```text
Actor profile
 -> graph/timeline request constrained by date, role, depth and result limit
 -> user clicks a link edge
 -> evidence drawer retrieves exact CandidateLink version + EvidenceUnits
 -> user accepts/rejects/defers link with mandatory note
 -> API creates new decision + audit event + timeline event
 -> UI refreshes current projected state
```

### Case to Export
```text
User adds actor/link/evidence to case
 -> case stores references, not mutable copies
 -> user requests export
 -> API checks authorization
 -> exporter snapshots exact IDs, versions, model/config hash and timestamps
 -> template renders JSON/CSV/PDF
 -> artifact/hash/manifest stored
 -> audit event written
 -> user receives allowed download
```

## 3. End-to-End Data Flow Pipeline

```text
1. Source policy checks fixture or approved source.
2. Collector replays/fetches content and creates Capture record.
3. Raw artifact is hashed (SHA-256) and stored in MinIO/fixture archive.
4. Normalizer validates MIME/size and produces safe text, or quarantines capture.
5. Adapters parse observations and emit validated EvidenceUnits (K/I/B/S).
6. Evidence records persist to canonical store (PostgreSQL) and update projections.
7. Resolver groups evidence by entity pair and independence group.
8. Fusion calculates category scores, final score, tier, limitations, and explanation.
9. CandidateLink version is written; conflict sets and timeline events update.
10. Dashboard requests redacted data through FastAPI REST APIs.
11. Analyst decision writes an immutable audit event and new relationship version.
12. Export snapshots selected versions and creates report artifact + audit record.
```

## 4. Canonical Schemas & Records

### Capture Record
```json
{
  "capture_id": "cap_20260905_001",
  "source_id": "fixture_market_a",
  "url": "fixture://market-a/profile/ghostvendor",
  "mode": "fixture_replay",
  "authorization_status": "approved",
  "captured_at": "2026-09-05T10:00:00Z",
  "source_claimed_time": "2026-09-01T08:00:00Z",
  "http_status": 200,
  "content_type": "text/html",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "raw_object_reference": "fixtures/market-a/ghostvendor.html",
  "status": "succeeded"
}
```

### Candidate Link Record
```json
{
  "link_id": "lnk_a1b2c3",
  "link_version": 1,
  "left_entity_id": "alias_ghostvendor",
  "right_entity_id": "alias_nightshade99",
  "state": "needs_review",
  "score": 0.63,
  "tier": "possible_association",
  "score_status": "observed",
  "category_breakdown": {
    "K": {"score": 0.0, "state": "not_available", "evidence_ids": []},
    "I": {"score": 0.18, "state": "observed", "evidence_ids": ["ev_101"]},
    "B": {"score": 0.56, "state": "observed", "evidence_ids": ["ev_102", "ev_103"]},
    "S": {"score": 0.46, "state": "observed", "evidence_ids": ["ev_104"]}
  },
  "explanation": "Association based on behavioral overlap and semantic similarity. Limitations: Text evidence is supporting only.",
  "limitations": [
    "Semantic similarity is supporting evidence only, not authorship proof.",
    "Infrastructure signal may reflect shared hosting."
  ],
  "score_model_version": "scoring-v1.0",
  "calculation_input_hash": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"
}
```

## 5. Persistence and Idempotency Rules

| Object | Idempotency Key | Unique Constraint |
|---|---|---|
| **Capture** | source + URL + content hash + capture time bucket | `UNIQUE(source_id, url, sha256, captured_at)` |
| **EvidenceUnit** | adapter source + capture ID + indicator type + indicator value + entity pair | `UNIQUE(source, source_version, capture_id, indicator_type, indicator_value, left_entity_id, right_entity_id)` |
| **CandidateLink** | canonical entity pair + score model version + calculation input hash | `UNIQUE(left_entity_id, right_entity_id, score_model_version, calculation_input_hash)` |
| **AuditEvent** | request ID + action + object ID + timestamp | `UNIQUE(request_id, action, object_id, timestamp)` |
| **Export** | case ID + selected version manifest hash | Returns existing export artifact if hash matches |

## 6. Minimal API Definitions

```text
POST /v1/search
GET  /v1/entities/{entity_type}/{entity_id}
GET  /v1/evidence/{evidence_id}
GET  /v1/actors/{actor_id}
GET  /v1/actors/{actor_id}/graph
GET  /v1/actors/{actor_id}/timeline
GET  /v1/links/{link_id}
POST /v1/links/{link_id}/decision
POST /v1/cases
POST /v1/cases/{case_id}/items
POST /v1/exports
GET  /v1/exports/{export_id}
GET  /v1/admin/sources
POST /v1/admin/sources
POST /v1/admin/kill-switch
GET  /v1/audit
```
