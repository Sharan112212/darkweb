from timeline.event_builder import TimelineEventBuilder, confidence_label
from models.evidence import EvidenceUnit


def _primary(events):
    return [e for e in events if e.event_type not in ("first_seen", "last_seen")][0]


def _ev(**kw):
    base = dict(
        evidence_id="ev_1", capture_id="cap_1", source="s", source_version="1.0.0",
        indicator_type="pgp_fingerprint", indicator_value="ABCD",
        linked_entities=["actor_a"], confidence_weight=0.9,
        captured_at="2026-08-01T00:00:00+00:00", source_url="http://x.onion",
        raw_evidence_hash="h", raw_evidence_reference="ref",
        independence_group_id="ig", explanation="e",
    )
    base.update(kw)
    return EvidenceUnit(**base)


def test_confidence_label_bands():
    assert confidence_label(1.0) == "exact"
    assert confidence_label(0.7) == "approximate"
    assert confidence_label(0.2) == "uncertain"


def test_forged_source_time_is_marked_approximate_not_definitive():
    # Low time_confidence claimed time (EC-16) must be flagged, not shown as exact.
    ev = _ev(source_claimed_time="2020-01-01T00:00:00+00:00", time_confidence=0.3)
    e = _primary(TimelineEventBuilder().build_from_evidence([ev], entity_id="actor_a"))
    assert e.metadata["approximate"] is True
    assert e.metadata["time_confidence_label"] in ("uncertain", "approximate")
    assert e.metadata["time_basis"] == "source_claimed_time"


def test_captured_time_is_exact_but_flagged_as_capture_basis():
    ev = _ev(time_confidence=1.0)
    e = _primary(TimelineEventBuilder().build_from_evidence([ev], entity_id="actor_a"))
    assert e.metadata["time_confidence_label"] == "exact"
    assert e.metadata["approximate"] is False
    assert e.metadata["time_basis"] == "captured_at"
