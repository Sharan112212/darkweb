# SIH26151 — Data Contracts & Schemas

This document specifies the frozen data contracts for `EvidenceUnit` and `CandidateLink`.

## 1. `EvidenceUnit` Contract

All evidence collection and analysis modules must output validated `EvidenceUnit` records through local adapters. No module-specific raw payload enters fusion directly.

```python
class EvidenceUnit(BaseModel):
    evidence_id: str                    # Unique ID (e.g. ev_pgp_8a9b0c)
    schema_version: str = "1.0.0"       # Contract schema version
    capture_id: str                     # Associated Capture record ID
    source: str                         # Source identifier (e.g. fixture_market_a)
    source_version: str                 # Version of source/collector
    indicator_type: str                 # Enum value (pgp_fingerprint, wallet_address, etc.)
    indicator_value: str                # Normalized indicator value
    indicator_role: Optional[str]       # key_published | verified_signature | wallet_unknown | etc.
    linked_entities: list[str]          # Exactly 2 entity IDs for pairwise candidate link
    confidence_weight: float            # Signal strength 0.0 to 1.0
    source_reliability: float = 1.0     # Source reliability weight 0.0 to 1.0
    extraction_confidence: float = 1.0  # Extraction accuracy weight 0.0 to 1.0
    source_claimed_time: Optional[str]  # Source claimed timestamp (ISO-8601 UTC)
    observation_date: Optional[str]    # Observed timestamp (ISO-8601 UTC)
    captured_at: str                    # System capture timestamp (ISO-8601 UTC)
    time_confidence: float = 1.0        # Timestamp confidence weight 0.0 to 1.0
    source_url: str                     # Source URL or reference
    raw_evidence_hash: str              # SHA-256 hash of raw input
    raw_evidence_reference: str         # MinIO / fixture reference path
    independence_group_id: str          # ID grouping duplicate/mirrored observations
    collector_mode: str = "fixture_replay" # fixture_replay | authorized_tor | authorized_clearnet
    processing_status: str = "valid"    # valid | quarantined | parse_failed | redacted | superseded
    explanation: str                    # Analyst-readable evidence explanation
    limitations: list[str]              # Caveats and limitation statements
    context_excerpt: Optional[str]      # Safe redacted excerpt
    model_metadata: dict                # Model/rule parameters used
```

## 2. `CandidateLink` Contract

```python
class CandidateLink(BaseModel):
    link_id: str                        # Candidate link ID (e.g. lnk_9f8e7d)
    link_version: int = 1               # Version number (increments on score/decision change)
    left_entity_id: str                 # Left entity ID (alphabetically first)
    right_entity_id: str                # Right entity ID (alphabetically second)
    state: str = "proposed"             # proposed | needs_review | accepted | rejected | superseded
    score: float                        # Final fused score 0.0 to 1.0
    tier: str                           # insufficient_evidence | unresolved | possible_association | likely_same_actor | observed_technical_identity
    score_status: str = "observed"      # observed | insufficient | conflicting | stale | not_available
    category_breakdown: dict            # K, I, B, S category scores, states, and evidence IDs
    evidence_ids: list[str]             # List of contributing EvidenceUnit IDs
    conflict_set_id: Optional[str]      # ID linking competing candidate hypotheses
    competing_link_ids: list[str]       # List of competing link IDs
    explanation: str                    # Deterministic explanation string
    limitations: list[str]              # Combined caveats across contributing evidence
    score_model_version: str = "scoring-v1.0" # Scoring algorithm version
    calculation_input_hash: str         # SHA-256 hash of sorted evidence IDs + config
    created_at: str                     # Initial creation timestamp (ISO-8601 UTC)
    updated_at: str                     # Last modification timestamp (ISO-8601 UTC)
```

## 3. Indicator Categories (K / I / B / S)

| Category | Code | Description | Max Contribution |
|---|---|---|---|
| **Cryptographic & Hard Identifiers** | **K** | PGP fingerprints, cryptocurrency wallet addresses, cryptographic keys, verified contact handles | Uncapped (up to 1.0) |
| **Infrastructure** | **I** | SSL certificate fingerprints, server status misconfigs, co-hosted domains, OnionScan findings | Capped (≤ Possible Association unless corroborated) |
| **Behavioral** | **B** | Posting-time histograms, vocabulary reuse, structural template hashes, source presence overlap | Capped (≤ Possible Association unless corroborated) |
| **Semantic & Stylometric** | **S** | Sentence-BERT semantic similarity, classical linguistic features (function words, n-grams, sentence length) | Capped (S max contribution ≤ 0.20 to final score) |
