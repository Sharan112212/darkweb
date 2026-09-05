from fusion.explainable_fusion import ExplainableFusionEngine
from models.evidence import EvidenceUnit

def test_hysteresis_boundary_stability():
    engine = ExplainableFusionEngine()

    u_pgp = EvidenceUnit(
        evidence_id="ev_pgp_1", capture_id="cap1", source="src", source_version="1",
        indicator_type="pgp_fingerprint", indicator_value="9A3F", linked_entities=["A", "B"],
        confidence_weight=0.71, captured_at="now", source_url="url", raw_evidence_hash="h",
        raw_evidence_reference="ref", independence_group_id="indep_pgp", explanation="pgp"
    )

    prev_link = engine.evaluate_pair("A", "B", [u_pgp])
    assert prev_link.tier == "likely_same_actor"

    # Slightly modified evidence score drops to 0.69 (within +-0.03 hysteresis margin)
    u_pgp_slight = EvidenceUnit(
        evidence_id="ev_pgp_1", capture_id="cap1", source="src", source_version="1",
        indicator_type="pgp_fingerprint", indicator_value="9A3F", linked_entities=["A", "B"],
        confidence_weight=0.69, captured_at="now", source_url="url", raw_evidence_hash="h",
        raw_evidence_reference="ref", independence_group_id="indep_pgp", explanation="pgp"
    )

    new_link = engine.evaluate_pair("A", "B", [u_pgp_slight], previous_link=prev_link)

    # Hysteresis retains previous tier 'likely_same_actor' to prevent flicker (EC-25)
    assert new_link.tier == "likely_same_actor"
