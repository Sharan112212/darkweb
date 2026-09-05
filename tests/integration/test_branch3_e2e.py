from collection.fixture_replayer import FixtureReplayer
from adapters.identity_evidence_adapter import IdentityEvidenceAdapter
from adapters.minilm_evidence_adapter import MiniLMEvidenceAdapter
from db.repositories.evidence_repo import EvidenceRepository
from fusion.explainable_fusion import ExplainableFusionEngine
from fusion.link_lifecycle import LinkLifecycleManager

def test_branch3_e2e_fusion_pipeline(temp_db):
    replayer = FixtureReplayer(db_path=temp_db)
    id_adapter = IdentityEvidenceAdapter()
    minilm_adapter = MiniLMEvidenceAdapter()
    evidence_repo = EvidenceRepository(temp_db)
    fusion_engine = ExplainableFusionEngine()
    lifecycle_mgr = LinkLifecycleManager(temp_db)

    # 1. Capture fixture
    capture, content = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")
    assert capture.status == "succeeded"

    # 2. Extract EvidenceUnits
    raw_payload_id = {
        "actor_a": "DarkFox",
        "actor_b": "DarkFox_v2",
        "evidence": "PGP Fingerprint: 9A3F 21B4 77C0 EE12 5D6A 8F90 11C3 4B22 FA01 9D77; Wallet Address: bc1qzp3d8x9k2m4h7j6n5w0e1r2t3y4u5i6o7p8a9",
        "signature_verified": True
    }
    raw_payload_sbert = {
        "actor_a": "DarkFox",
        "actor_b": "DarkFox_v2",
        "similarity": 0.7906,
        "post_count_a": 10, "post_count_b": 10,
        "char_count_a": 2000, "char_count_b": 2000
    }

    units_id = id_adapter.extract(raw_payload_id)
    units_sbert = minilm_adapter.extract(raw_payload_sbert)
    all_units = units_id + units_sbert

    # 3. Save to EvidenceRepository
    for u in all_units:
        evidence_repo.save(u)

    # 4. Evaluate pair using ExplainableFusionEngine
    candidate_link = fusion_engine.evaluate_pair("DarkFox", "DarkFox_v2", all_units)

    assert candidate_link.score >= 0.90
    assert candidate_link.tier == "observed_technical_identity"
    assert candidate_link.category_breakdown["K"]["state"] == "observed"
    assert candidate_link.category_breakdown["S"]["state"] == "observed"

    # 5. Link Lifecycle state transition & version persistence
    accepted_link = lifecycle_mgr.transition_state(candidate_link, "accepted", user_id="lead_analyst", reason="Confirmed multi-vector match")
    assert accepted_link.state == "accepted"
    assert accepted_link.link_version == 2
