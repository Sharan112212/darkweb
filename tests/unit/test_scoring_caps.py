from fusion.explainable_fusion import ExplainableFusionEngine
from models.evidence import EvidenceUnit

def test_text_only_scoring_cap():
    engine = ExplainableFusionEngine()

    u_sem = EvidenceUnit(
        evidence_id="ev_sem_1", capture_id="cap1", source="src", source_version="1",
        indicator_type="semantic_similarity", indicator_value="0.99", linked_entities=["GhostVendor", "Nightshade99"],
        confidence_weight=0.20, captured_at="now", source_url="url", raw_evidence_hash="h",
        raw_evidence_reference="ref", independence_group_id="indep_sem", explanation="sem"
    )

    link = engine.evaluate_pair("GhostVendor", "Nightshade99", [u_sem])

    # Text-only evidence capped at Category S max contribution (<= 0.20) or Possible Association (<= 0.65)
    assert link.score <= 0.65
    assert link.tier != "observed_technical_identity"
    assert link.tier != "likely_same_actor"
