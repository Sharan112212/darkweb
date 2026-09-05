"""
Integration test: Branch 2 End-to-End Pipeline.
Validates the complete chain:
Collection (FixtureReplayer / CaptureManager)
  -> Capture record creation & SHA-256 computation
  -> Normalization (MIME validation, size cap, safe parsing)
  -> Evidence Extraction (IdentityEvidenceAdapter)
  -> Canonical Persistence (EvidenceRepository)
  -> Query & Retrieval
Also tests quarantine branch (EC-03) and offline status retention branch (EC-01).
"""
from collection.fixture_replayer import FixtureReplayer
from collection.normalizer import CollectionNormalizer
from adapters.identity_evidence_adapter import IdentityEvidenceAdapter
from db.repositories.capture_repo import CaptureRepository
from db.repositories.evidence_repo import EvidenceRepository


def test_branch2_e2e_collection_pipeline(temp_db):
    """Test full happy-path collection -> capture -> normalize -> adapter pipeline."""
    replayer = FixtureReplayer(db_path=temp_db)
    normalizer = CollectionNormalizer()
    adapter = IdentityEvidenceAdapter()
    evidence_repo = EvidenceRepository(temp_db)
    capture_repo = CaptureRepository(temp_db)

    # 1. Collection & Capture creation
    capture, content_bytes = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")
    assert capture.status == "succeeded"
    assert capture.http_status == 200
    assert len(capture.sha256) == 64
    assert capture_repo.get_by_id(capture.capture_id) is not None

    # 2. Normalization & Safe parsing (no JS execution)
    safe_text, meta = normalizer.normalize(content_bytes, content_type="text/html")
    assert meta["status"] == "valid"
    assert "<script>" not in safe_text
    assert "GhostVendor" in safe_text

    # 3. Adapter extraction emitting canonical EvidenceUnits
    raw_payload = {
        "actor_a": "GhostVendor",
        "actor_b": "Nightshade99",
        "evidence": "PGP Fingerprint: 1122 33AA BBCC DD44 5566 7788 99EE FF00 1234 5678; Wallet Address: 3GhostVendorFakeWallet000000000000",
        "capture_id": capture.capture_id,
        "source_url": capture.url,
        "source": "market-a",
    }
    units = adapter.extract(raw_payload)
    assert len(units) == 2

    # Verify canonical EvidenceUnit fields
    for u in units:
        assert u.capture_id == capture.capture_id
        assert u.category == "K"
        assert u.processing_status == "valid"
        assert u.independence_group_id.startswith("indep_")
        assert len(u.linked_entities) == 2
        assert u.validate_for_candidate_link() is True

    # 4. Persistence into canonical EvidenceRepository
    for u in units:
        evidence_repo.save(u)

    # 5. Retrieval verification
    retrieved = evidence_repo.list_by_pair("GhostVendor", "Nightshade99")
    assert len(retrieved) == 2
    types = {r.indicator_type for r in retrieved}
    assert "pgp_fingerprint" in types
    assert "wallet_address" in types


def test_branch2_e2e_quarantine_pipeline_ec03(temp_db):
    """Test end-to-end quarantine path for oversized content (>10MB) per EC-03."""
    replayer = FixtureReplayer(db_path=temp_db)
    normalizer = CollectionNormalizer()
    evidence_repo = EvidenceRepository(temp_db)

    # 1. Fetch oversized fixture (>10MB)
    capture, content_bytes = replayer.fetch_fixture("fixture://market-b/oversized.html")
    assert len(content_bytes) > 10 * 1024 * 1024

    # 2. Normalization intercepts and flags quarantine
    safe_text, meta = normalizer.normalize(content_bytes, content_type="text/html")
    assert meta["status"] == "quarantined"
    assert "10mb" in meta["reason"].lower() or "exceeds" in meta["reason"].lower()
    # Safe text must be empty for quarantined content
    assert safe_text == ""

    # 3. Verify no unparsed evidence enters the repository
    assert evidence_repo.count() == 0


def test_branch2_e2e_offline_transition_pipeline_ec01(temp_db):
    """Test end-to-end offline source handling retaining prior evidence per EC-01."""
    replayer = FixtureReplayer(db_path=temp_db)
    adapter = IdentityEvidenceAdapter()
    evidence_repo = EvidenceRepository(temp_db)

    # 1. Online capture and evidence storage
    cap1, _ = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")
    payload = {
        "actor_a": "GhostVendor",
        "actor_b": "Nightshade99",
        "evidence": "PGP Fingerprint: 1122 33AA BBCC DD44 5566 7788 99EE FF00 1234 5678",
        "capture_id": cap1.capture_id,
        "source_url": cap1.url,
    }
    units = adapter.extract(payload)
    for u in units:
        evidence_repo.save(u)
    assert evidence_repo.count() == 1

    # 2. Source returns 503 offline
    cap2, _ = replayer.fetch_fixture("fixture://market-a/ghostvendor_offline.html")
    assert cap2.status == "failed"
    assert cap2.http_status == 503

    # 3. Verify prior evidence remains intact and accessible
    assert evidence_repo.count() == 1
    retained = evidence_repo.list_by_pair("GhostVendor", "Nightshade99")
    assert len(retained) == 1
    assert retained[0].capture_id == cap1.capture_id
