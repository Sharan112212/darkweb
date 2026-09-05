from fusion.explainable_fusion import ExplainableFusionEngine
from models.evidence import EvidenceUnit

def test_fusion_engine_multi_signal_boost():
    engine = ExplainableFusionEngine()

    u_pgp = EvidenceUnit(
        evidence_id="ev_pgp_1", capture_id="cap1", source="src", source_version="1",
        indicator_type="pgp_fingerprint", indicator_value="9A3F", linked_entities=["DarkFox", "DarkFox_v2"],
        confidence_weight=0.95, captured_at="now", source_url="url", raw_evidence_hash="h",
        raw_evidence_reference="ref", independence_group_id="indep_pgp", explanation="pgp"
    )
    u_sem = EvidenceUnit(
        evidence_id="ev_sem_1", capture_id="cap1", source="src", source_version="1",
        indicator_type="semantic_similarity", indicator_value="0.85", linked_entities=["DarkFox", "DarkFox_v2"],
        confidence_weight=0.18, captured_at="now", source_url="url", raw_evidence_hash="h",
        raw_evidence_reference="ref", independence_group_id="indep_sem", explanation="sem"
    )

    link = engine.evaluate_pair("DarkFox", "DarkFox_v2", [u_pgp, u_sem])

    assert link.score >= 0.90
    assert link.tier == "observed_technical_identity"
    assert link.calculation_input_hash.startswith("sha256:")
    assert len(link.evidence_ids) == 2
