from enum import Enum

class CollectorMode(str, Enum):
    fixture_replay = "fixture_replay"
    authorized_tor = "authorized_tor"
    authorized_clearnet = "authorized_clearnet"

class ProcessingStatus(str, Enum):
    valid = "valid"
    quarantined = "quarantined"
    parse_failed = "parse_failed"
    redacted = "redacted"
    superseded = "superseded"

class IndicatorType(str, Enum):
    pgp_fingerprint = "pgp_fingerprint"
    wallet_address = "wallet_address"
    alias = "alias"
    contact_identifier = "contact_identifier"
    certificate_fingerprint = "certificate_fingerprint"
    infrastructure_match = "infrastructure_match"
    onionscan_analytics_id = "onionscan_analytics_id"
    onionscan_exif_leak = "onionscan_exif_leak"
    onionscan_server_status = "onionscan_server_status"
    onionscan_ssh_key = "onionscan_ssh_key"
    onionscan_certificate = "onionscan_certificate"
    onionscan_open_directory = "onionscan_open_directory"
    semantic_similarity = "semantic_similarity"
    classical_stylometry = "classical_stylometry"
    posting_time_pattern = "posting_time_pattern"
    vocabulary_overlap = "vocabulary_overlap"
    template_match = "template_match"
    persona_migration_candidate = "persona_migration_candidate"

class IndicatorRole(str, Enum):
    key_published = "key_published"
    verified_signature = "verified_signature"
    wallet_unknown = "wallet_unknown"
    shared_service_wallet = "shared_service_wallet"
    mixer_suspected = "mixer_suspected"

class LinkState(str, Enum):
    proposed = "proposed"
    needs_review = "needs_review"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"

class Tier(str, Enum):
    insufficient_evidence = "insufficient_evidence"
    unresolved = "unresolved"
    possible_association = "possible_association"
    likely_same_actor = "likely_same_actor"
    observed_technical_identity = "observed_technical_identity"

class ScoreStatus(str, Enum):
    observed = "observed"
    insufficient = "insufficient"
    conflicting = "conflicting"
    stale = "stale"
    not_available = "not_available"

class UserRole(str, Enum):
    viewer = "viewer"
    analyst = "analyst"
    reviewer = "reviewer"
    admin = "admin"
