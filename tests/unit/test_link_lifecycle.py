import pytest
from fusion.link_lifecycle import LinkLifecycleManager
from fusion.explainable_fusion import ExplainableFusionEngine
from models.evidence import EvidenceUnit

def test_link_lifecycle_transitions(temp_db):
    mgr = LinkLifecycleManager(temp_db)
    engine = ExplainableFusionEngine()

    u = EvidenceUnit(
        evidence_id="ev_1", capture_id="c1", source="s", source_version="1",
        indicator_type="pgp_fingerprint", indicator_value="KEY1", linked_entities=["DarkFox", "DarkFox_v2"],
        confidence_weight=0.95, captured_at="now", source_url="u", raw_evidence_hash="h",
        raw_evidence_reference="r", independence_group_id="g1", explanation="e"
    )

    link = engine.evaluate_pair("DarkFox", "DarkFox_v2", [u])
    assert link.state == "proposed"

    # Transition to needs_review
    link_v2 = mgr.transition_state(link, "needs_review", user_id="analyst1", reason="Under review")
    assert link_v2.state == "needs_review"
    assert link_v2.link_version == 2

    # Transition to accepted
    link_v3 = mgr.transition_state(link_v2, "accepted", user_id="reviewer1", reason="Confirmed by reviewer")
    assert link_v3.state == "accepted"
    assert link_v3.link_version == 3

    # Invalid transition (superseded to accepted not allowed)
    link_v3.state = "superseded"
    with pytest.raises(ValueError):
        mgr.transition_state(link_v3, "accepted", user_id="analyst1", reason="Invalid")
