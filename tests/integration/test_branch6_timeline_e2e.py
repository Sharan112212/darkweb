import pytest
from timeline.event_builder import TimelineEventBuilder
from db.repositories.timeline_repo import TimelineRepository
from models.evidence import EvidenceUnit


def _ev(evidence_id, indicator_type, captured_at, entities=("actor_a", "actor_b"), **kw):
    base = dict(
        evidence_id=evidence_id, capture_id="cap_1", source="identity_graph",
        source_version="1.0.0", indicator_type=indicator_type, indicator_value="v",
        linked_entities=list(entities), confidence_weight=0.9, captured_at=captured_at,
        source_url="http://x.onion", raw_evidence_hash="h", raw_evidence_reference="ref",
        independence_group_id="ig", explanation="e",
    )
    base.update(kw)
    return EvidenceUnit(**base)


def test_branch6_timeline_evidence_to_persist_and_query(temp_db):
    # 1. Build timeline events from evidence for actor_a
    builder = TimelineEventBuilder()
    evidence = [
        _ev("ev_pgp", "pgp_fingerprint", "2026-06-01T00:00:00+00:00"),
        _ev("ev_wal", "wallet_address", "2026-07-01T00:00:00+00:00"),
        _ev("ev_onion", "onionscan_certificate", "2026-08-01T00:00:00+00:00"),
    ]
    events = builder.build_from_evidence(evidence, entity_id="actor_a")

    # >= 3 distinct event types (acceptance criterion)
    assert len({e.event_type for e in events}) >= 3

    # 2. Persist via repository
    repo = TimelineRepository(temp_db)
    written = builder.persist(events, repo)
    assert written == len(events)

    # 3. Query back, chronological
    stored = repo.list_by_entity("actor_a")
    assert len(stored) == len(events)
    timestamps = [s["timestamp"] for s in stored]
    assert timestamps == sorted(timestamps)

    # 4. Date-filter consistency (same bound the graph view would use)
    in_july = [s for s in stored if "2026-06-15T00:00:00+00:00" <= s["timestamp"] <= "2026-07-15T00:00:00+00:00"]
    assert any(s["event_type"] == "wallet_seen" for s in in_july)
