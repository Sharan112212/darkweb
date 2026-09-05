import pytest
from timeline.event_builder import TimelineEventBuilder
from models.evidence import EvidenceUnit
from models.candidate_link import CandidateLink


def _ev(**kw):
    base = dict(
        evidence_id="ev_1",
        capture_id="cap_1",
        source="identity_graph",
        source_version="1.0.0",
        indicator_type="pgp_fingerprint",
        indicator_value="ABCD",
        linked_entities=["actor_a", "actor_b"],
        confidence_weight=0.9,
        captured_at="2026-08-01T00:00:00+00:00",
        source_url="http://x.onion",
        raw_evidence_hash="h",
        raw_evidence_reference="ref",
        independence_group_id="ig_1",
        explanation="shared pgp",
    )
    base.update(kw)
    return EvidenceUnit(**base)


def _primary(events):
    """First non-bookend event (excludes derived first_seen/last_seen)."""
    return [e for e in events if e.event_type not in ("first_seen", "last_seen")][0]


def _link(**kw):
    base = dict(
        link_id="link_1",
        left_entity_id="actor_a",
        right_entity_id="actor_b",
        score=0.82,
        tier="likely_same_actor",
        explanation="shared pgp",
        calculation_input_hash="cih",
        created_at="2026-08-05T00:00:00+00:00",
        updated_at="2026-08-06T00:00:00+00:00",
    )
    base.update(kw)
    return CandidateLink(**base)


def test_build_from_evidence_emits_event_per_entity_plus_bookends():
    b = TimelineEventBuilder()
    events = b.build_from_evidence([_ev()])
    types = {e.event_type for e in events}
    assert "pgp_seen" in types
    assert "first_seen" in types and "last_seen" in types
    # one pgp_seen per linked entity (2)
    assert sum(1 for e in events if e.event_type == "pgp_seen") == 2


def test_indicator_type_maps_to_event_type():
    b = TimelineEventBuilder()
    assert _primary(b.build_from_evidence([_ev(indicator_type="wallet_address", evidence_id="ev_w")], entity_id="actor_a")).event_type == "wallet_seen"
    assert _primary(b.build_from_evidence([_ev(indicator_type="onionscan_ssh_key", evidence_id="ev_o")], entity_id="actor_a")).event_type == "infrastructure_observation"


def test_entity_filter_limits_events():
    b = TimelineEventBuilder()
    events = b.build_from_evidence([_ev()], entity_id="actor_a")
    assert all(e.entity_id == "actor_a" for e in events)


def test_prefers_source_claimed_time_then_observation_then_captured():
    b = TimelineEventBuilder()
    ev = _ev(source_claimed_time="2026-01-01T00:00:00+00:00",
             observation_date="2026-02-01T00:00:00+00:00", time_confidence=0.4)
    e = _primary(b.build_from_evidence([ev], entity_id="actor_a"))
    assert e.timestamp == "2026-01-01T00:00:00+00:00"
    assert e.metadata["time_basis"] == "source_claimed_time"

    ev2 = _ev(observation_date="2026-02-01T00:00:00+00:00")
    e2 = _primary(b.build_from_evidence([ev2], entity_id="actor_a"))
    assert e2.metadata["time_basis"] == "observation_date"

    ev3 = _ev()
    e3 = _primary(b.build_from_evidence([ev3], entity_id="actor_a"))
    assert e3.metadata["time_basis"] == "captured_at"


def test_never_invents_dates_uses_only_present_fields():
    b = TimelineEventBuilder()
    ev = _ev(source_claimed_time=None, observation_date=None, captured_at="2026-08-01T00:00:00+00:00")
    e = _primary(b.build_from_evidence([ev], entity_id="actor_a"))
    assert e.timestamp == "2026-08-01T00:00:00+00:00"


def test_build_from_link_creates_lifecycle_events():
    b = TimelineEventBuilder()
    link = _link(state="accepted", link_version=2)
    events = b.build_from_link(link)
    types = {e.event_type for e in events}
    assert "candidate_link_created" in types
    assert "score_change" in types
    assert "analyst_decision" in types


def test_empty_evidence_returns_empty_list():
    assert TimelineEventBuilder().build_from_evidence([]) == []
