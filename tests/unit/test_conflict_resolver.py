from fusion.conflict_resolver import ConflictResolver
from fusion.explainable_fusion import ExplainableFusionEngine
from models.evidence import EvidenceUnit

def test_conflict_resolver_competing_hypotheses():
    engine = ExplainableFusionEngine()

    u1 = EvidenceUnit(
        evidence_id="ev_1", capture_id="c1", source="s", source_version="1",
        indicator_type="pgp_fingerprint", indicator_value="KEY1", linked_entities=["ActorA", "ActorB"],
        confidence_weight=0.90, captured_at="now", source_url="u", raw_evidence_hash="h",
        raw_evidence_reference="r", independence_group_id="g1", explanation="e"
    )
    u2 = EvidenceUnit(
        evidence_id="ev_2", capture_id="c1", source="s", source_version="1",
        indicator_type="pgp_fingerprint", indicator_value="KEY2", linked_entities=["ActorA", "ActorC"],
        confidence_weight=0.90, captured_at="now", source_url="u", raw_evidence_hash="h",
        raw_evidence_reference="r", independence_group_id="g2", explanation="e"
    )

    link1 = engine.evaluate_pair("ActorA", "ActorB", [u1])
    link2 = engine.evaluate_pair("ActorA", "ActorC", [u2])

    resolved = ConflictResolver.resolve_conflicts([link1, link2])

    assert resolved[0].conflict_set_id is not None
    assert resolved[0].conflict_set_id == resolved[1].conflict_set_id
    assert resolved[0].competing_link_ids == [resolved[1].link_id]
