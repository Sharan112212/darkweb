from db.repositories.evidence_repo import EvidenceRepository
from db.repositories.link_repo import LinkRepository
from adapters.identity_evidence_adapter import IdentityEvidenceAdapter
from adapters.legacy_fusion_adapter import LegacyFusionAdapter

def test_branch1_e2e_pipeline(temp_db):
    evidence_repo = EvidenceRepository(temp_db)
    link_repo = LinkRepository(temp_db)
    identity_adapter = IdentityEvidenceAdapter()

    # 1. Simulate existing identity graph raw payload
    raw_payload = {
        "actor_a": "DarkFox",
        "actor_b": "DarkFox_v2",
        "evidence": "PGP Fingerprint: 9A3F 21B4 77C0 EE12 5D6A 8F90 11C3 4B22 FA01 9D77; Wallet Address: bc1qzp3d8x9k2m4h7j6n5w0e1r2t3y4u5i6o7p8a9",
        "signature_verified": True
    }

    # 2. Extract canonical EvidenceUnits via adapter
    evidence_units = identity_adapter.extract(raw_payload)
    assert len(evidence_units) == 2

    # 3. Persist EvidenceUnits into repository
    saved_units = [evidence_repo.save(unit) for unit in evidence_units]
    assert len(saved_units) == 2

    # 4. Verify round-trip retrieval by entity pair
    retrieved = evidence_repo.list_by_pair("DarkFox", "DarkFox_v2")
    assert len(retrieved) == 2

    # 5. Verify bridge adapter conversion for legacy fusion compatibility
    legacy_links = [LegacyFusionAdapter.to_legacy_link(u) for u in retrieved]
    assert len(legacy_links) == 2
    assert legacy_links[0][0] == "DarkFox"
    assert legacy_links[0][1] == "DarkFox_v2"
    assert legacy_links[0][2] == "shared_identifier"
