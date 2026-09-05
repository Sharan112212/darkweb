-- SIH26151 Dark-Web Threat Actor Attribution Platform
-- Canonical Schema DDL (PostgreSQL & SQLite Compatible)
-- Conforms to App Data Flow §4, §5 & §6

-- 1. Captures Table: Raw ingestion and scraper capture metadata
CREATE TABLE IF NOT EXISTS captures (
    capture_id VARCHAR(64) PRIMARY KEY,
    source_id VARCHAR(128) NOT NULL,
    url TEXT NOT NULL,
    mode VARCHAR(64) NOT NULL,
    authorization_status VARCHAR(64) NOT NULL,
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source_claimed_time TIMESTAMP WITH TIME ZONE,
    http_status INTEGER,
    content_type VARCHAR(128),
    sha256 VARCHAR(64),
    raw_object_reference TEXT,
    status VARCHAR(64) NOT NULL,
    not_collected_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_capture_idempotency UNIQUE (source_id, url, sha256, captured_at)
);

-- 2. Entities Table: Canonical and normalized entities/actors
CREATE TABLE IF NOT EXISTS entities (
    entity_id VARCHAR(128) PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    canonical_name VARCHAR(256) NOT NULL,
    display_name VARCHAR(256),
    normalized_name VARCHAR(256),
    category VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Evidence Units Table: Atomic normalized multi-source evidence observations
CREATE TABLE IF NOT EXISTS evidence_units (
    evidence_id VARCHAR(64) PRIMARY KEY,
    schema_version VARCHAR(32) NOT NULL DEFAULT '1.0',
    capture_id VARCHAR(64),
    source VARCHAR(128) NOT NULL,
    source_version VARCHAR(64) NOT NULL DEFAULT '1.0',
    indicator_type VARCHAR(64) NOT NULL,
    indicator_value TEXT NOT NULL,
    indicator_role VARCHAR(64),
    left_entity_id VARCHAR(128) NOT NULL,
    right_entity_id VARCHAR(128) NOT NULL,
    confidence_weight DOUBLE PRECISION DEFAULT 1.0,
    source_reliability DOUBLE PRECISION DEFAULT 1.0,
    extraction_confidence DOUBLE PRECISION DEFAULT 1.0,
    source_claimed_time TIMESTAMP WITH TIME ZONE,
    observation_date TIMESTAMP WITH TIME ZONE,
    captured_at TIMESTAMP WITH TIME ZONE,
    time_confidence VARCHAR(64),
    source_url TEXT,
    raw_evidence_hash VARCHAR(64),
    raw_evidence_reference TEXT,
    independence_group_id VARCHAR(128),
    collector_mode VARCHAR(64),
    processing_status VARCHAR(64) DEFAULT 'processed',
    explanation TEXT,
    limitations_json JSONB DEFAULT '[]',
    context_excerpt TEXT,
    model_metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_evidence_idempotency UNIQUE (
        source,
        source_version,
        capture_id,
        indicator_type,
        indicator_value,
        left_entity_id,
        right_entity_id
    )
);

-- 4. Candidate Links Table: Fused correlation links between entity pairs
CREATE TABLE IF NOT EXISTS candidate_links (
    link_id VARCHAR(64) PRIMARY KEY,
    link_version INTEGER NOT NULL DEFAULT 1,
    left_entity_id VARCHAR(128) NOT NULL,
    right_entity_id VARCHAR(128) NOT NULL,
    state VARCHAR(64) NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    tier VARCHAR(64) NOT NULL,
    score_status VARCHAR(64) NOT NULL,
    category_breakdown_json JSONB DEFAULT '{}',
    evidence_ids_json JSONB DEFAULT '[]',
    conflict_set_id VARCHAR(64),
    competing_link_ids_json JSONB DEFAULT '[]',
    explanation TEXT,
    limitations_json JSONB DEFAULT '[]',
    score_model_version VARCHAR(64) NOT NULL,
    calculation_input_hash VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_candidate_links_idempotency UNIQUE (
        left_entity_id,
        right_entity_id,
        score_model_version,
        calculation_input_hash
    )
);

-- 5. Candidate Link Versions Table: Immutable historical snapshots of link decisions/scores
CREATE TABLE IF NOT EXISTS candidate_link_versions (
    version_id VARCHAR(64) PRIMARY KEY,
    link_id VARCHAR(64) NOT NULL REFERENCES candidate_links(link_id) ON DELETE CASCADE,
    link_version INTEGER NOT NULL,
    state VARCHAR(64) NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    tier VARCHAR(64) NOT NULL,
    category_breakdown_json JSONB DEFAULT '{}',
    evidence_ids_json JSONB DEFAULT '[]',
    explanation TEXT,
    limitations_json JSONB DEFAULT '[]',
    calculation_input_hash VARCHAR(128) NOT NULL,
    changed_by VARCHAR(128),
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_candidate_link_versions UNIQUE (link_id, link_version)
);

-- 6. Audit Events Table: Immutable security, access, and analyst decision logs
CREATE TABLE IF NOT EXISTS audit_events (
    event_id VARCHAR(64) PRIMARY KEY,
    request_id VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    action VARCHAR(64) NOT NULL,
    object_id VARCHAR(128) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details_json JSONB DEFAULT '{}',
    CONSTRAINT uq_audit_idempotency UNIQUE (request_id, action, object_id, timestamp)
);

-- 7. Timeline Events Table: Chronological activity and attribution events for entities
CREATE TABLE IF NOT EXISTS timeline_events (
    event_id VARCHAR(64) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(128) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    time_confidence VARCHAR(64),
    description TEXT,
    evidence_ids_json JSONB DEFAULT '[]',
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_captures_source ON captures(source_id);
CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_evidence_left_right ON evidence_units(left_entity_id, right_entity_id);
CREATE INDEX IF NOT EXISTS idx_evidence_capture ON evidence_units(capture_id);
CREATE INDEX IF NOT EXISTS idx_evidence_indicator ON evidence_units(indicator_type, indicator_value);
CREATE INDEX IF NOT EXISTS idx_candidate_links_pair ON candidate_links(left_entity_id, right_entity_id);
CREATE INDEX IF NOT EXISTS idx_candidate_links_state ON candidate_links(state);
CREATE INDEX IF NOT EXISTS idx_candidate_links_tier ON candidate_links(tier);
CREATE INDEX IF NOT EXISTS idx_candidate_link_versions_link ON candidate_link_versions(link_id);
CREATE INDEX IF NOT EXISTS idx_audit_object ON audit_events(object_id);
CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_events(request_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_id);
CREATE INDEX IF NOT EXISTS idx_timeline_entity ON timeline_events(entity_id);
CREATE INDEX IF NOT EXISTS idx_timeline_timestamp ON timeline_events(timestamp);
