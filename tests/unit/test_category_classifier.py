from fusion.category_classifier import CategoryClassifier
from models.evidence import EvidenceUnit

def test_category_classification():
    u_pgp = EvidenceUnit(
        evidence_id="ev_pgp", capture_id="cap1", source="src", source_version="1",
        indicator_type="pgp_fingerprint", indicator_value="9A3F", linked_entities=["A", "B"],
        confidence_weight=0.95, captured_at="now", source_url="url", raw_evidence_hash="h",
        raw_evidence_reference="ref", independence_group_id="indep1", explanation="pgp"
    )
    assert CategoryClassifier.classify(u_pgp) == "K"

    u_cert = EvidenceUnit(
        evidence_id="ev_cert", capture_id="cap1", source="src", source_version="1",
        indicator_type="certificate_fingerprint", indicator_value="abc", linked_entities=["A", "B"],
        confidence_weight=0.77, captured_at="now", source_url="url", raw_evidence_hash="h",
        raw_evidence_reference="ref", independence_group_id="indep2", explanation="cert"
    )
    assert CategoryClassifier.classify(u_cert) == "I"

    u_semantic = EvidenceUnit(
        evidence_id="ev_sem", capture_id="cap1", source="src", source_version="1",
        indicator_type="semantic_similarity", indicator_value="0.85", linked_entities=["A", "B"],
        confidence_weight=0.73, captured_at="now", source_url="url", raw_evidence_hash="h",
        raw_evidence_reference="ref", independence_group_id="indep3", explanation="sem"
    )
    assert CategoryClassifier.classify(u_semantic) == "S"
