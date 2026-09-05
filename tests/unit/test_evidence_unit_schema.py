import pytest
from pydantic import ValidationError
from models.evidence import EvidenceUnit

def test_valid_evidence_unit():
    unit = EvidenceUnit(
        evidence_id="ev_test_101",
        schema_version="1.0.0",
        capture_id="cap_001",
        source="test_source",
        source_version="1.0.0",
        indicator_type="pgp_fingerprint",
        indicator_value="9A3F21B477C0EE125D6A8F9011C34B22FA019D77",
        indicator_role="key_published",
        linked_entities=["DarkFox", "DarkFox_v2"],
        confidence_weight=0.95,
        source_reliability=1.0,
        extraction_confidence=1.0,
        captured_at="2026-09-05T10:00:00Z",
        source_url="http://test.onion/user/DarkFox",
        raw_evidence_hash="sha256:abc123hash",
        raw_evidence_reference="fixtures/market-a/ghostvendor.html",
        independence_group_id="indep_001",
        explanation="Test PGP match explanation",
        limitations=["Published key is not proof of key control"]
    )
    assert unit.evidence_id == "ev_test_101"
    assert unit.confidence_weight == 0.95
    assert len(unit.linked_entities) == 2

def test_invalid_confidence_weight():
    with pytest.raises(ValidationError):
        EvidenceUnit(
            evidence_id="ev_invalid",
            capture_id="cap_001",
            source="test_source",
            source_version="1.0.0",
            indicator_type="pgp_fingerprint",
            indicator_value="9A3F",
            linked_entities=["A", "B"],
            confidence_weight=1.5, # Out of range (0.0 to 1.0)
            captured_at="2026-09-05T10:00:00Z",
            source_url="http://test.onion",
            raw_evidence_hash="hash",
            raw_evidence_reference="ref",
            independence_group_id="indep",
            explanation="Invalid confidence test"
        )

def test_empty_linked_entities():
    with pytest.raises(ValidationError):
        EvidenceUnit(
            evidence_id="ev_no_links",
            capture_id="cap_001",
            source="test_source",
            source_version="1.0.0",
            indicator_type="pgp_fingerprint",
            indicator_value="9A3F",
            linked_entities=[], # Invalid: empty list
            confidence_weight=0.9,
            captured_at="2026-09-05T10:00:00Z",
            source_url="http://test.onion",
            raw_evidence_hash="hash",
            raw_evidence_reference="ref",
            independence_group_id="indep",
            explanation="Empty linked entities test"
        )
