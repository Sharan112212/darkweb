from collection.fixture_replayer import FixtureReplayer
from collection.normalizer import CollectionNormalizer
from adapters.identity_evidence_adapter import IdentityEvidenceAdapter
from db.repositories.evidence_repo import EvidenceRepository

def test_branch2_e2e_collection_pipeline(temp_db):
    replayer = FixtureReplayer(db_path=temp_db)
    normalizer = CollectionNormalizer()
    adapter = IdentityEvidenceAdapter()
    evidence_repo = EvidenceRepository(temp_db)

    # 1. Replay fixture and capture raw content
    capture, content_bytes = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")
    assert capture.status == "succeeded"

    # 2. Normalize raw content
    safe_text, meta = normalizer.normalize(content_bytes)
    assert meta["status"] == "valid"
    assert "<script>" not in safe_text

    # 3. Extract evidence via identity adapter
    raw_payload = {
        "actor_a": "GhostVendor",
        "actor_b": "Nightshade99",
        "evidence": "PGP Fingerprint: 1122 33AA BBCC DD44 5566 7788 99EE FF00 1234 5678; Wallet Address: 3GhostVendorFakeWallet000000000000",
        "capture_id": capture.capture_id,
        "source_url": capture.url
    }
    units = adapter.extract(raw_payload)
    assert len(units) == 2

    # 4. Save EvidenceUnits to repository
    for u in units:
        evidence_repo.save(u)

    # 5. Verify database storage
    saved = evidence_repo.list_by_pair("GhostVendor", "Nightshade99")
    assert len(saved) == 2
