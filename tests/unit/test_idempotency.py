from db.repositories.evidence_repo import EvidenceRepository
from models.evidence import EvidenceUnit

def test_evidence_idempotency(temp_db):
    repo = EvidenceRepository(temp_db)

    unit = EvidenceUnit(
        evidence_id="ev_idempotent_001",
        schema_version="1.0.0",
        capture_id="cap_001",
        source="test_source",
        source_version="1.0.0",
        indicator_type="pgp_fingerprint",
        indicator_value="9A3F21B477C0EE125D6A8F9011C34B22FA019D77",
        linked_entities=["DarkFox", "DarkFox_v2"],
        confidence_weight=0.95,
        captured_at="2026-09-05T10:00:00Z",
        source_url="http://test.onion/user/DarkFox",
        raw_evidence_hash="sha256:abc123hash",
        raw_evidence_reference="fixtures/market-a/ghostvendor.html",
        independence_group_id="indep_001",
        explanation="Test PGP match"
    )

    # First save: creates record
    res1 = repo.save(unit)
    assert res1.evidence_id == "ev_idempotent_001"

    # Second save (duplicate): must return existing record without error or duplication
    res2 = repo.save(unit)
    assert res2.evidence_id == "ev_idempotent_001"

    # Check database count
    all_units = repo.list_all()
    assert len(all_units) == 1
