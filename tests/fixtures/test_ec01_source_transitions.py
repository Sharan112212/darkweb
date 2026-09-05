"""
Fixture and edge-case test: EC-01 Source Transitions.
Tests the state progression: online -> offline (503) -> changed content.
Verifies durable capture status event creation, retry/failure recording,
and strict preservation of historical evidence units (no prior evidence deleted when source disappears).
"""
from collection.fixture_replayer import FixtureReplayer
from adapters.identity_evidence_adapter import IdentityEvidenceAdapter
from db.repositories.evidence_repo import EvidenceRepository


def test_ec01_source_transitions_and_evidence_retention(temp_db):
    """
    EC-01: Source timeout/offline/moved/503.
    Required control: Status event, retain history, bounded retries.
    Never delete prior evidence because a source disappears.
    """
    replayer = FixtureReplayer(db_path=temp_db)
    evidence_repo = EvidenceRepository(temp_db)
    adapter = IdentityEvidenceAdapter()

    # -------------------------------------------------------------
    # 1. Online: Normal operational capture from primary source
    # -------------------------------------------------------------
    cap1, content1 = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")
    assert cap1.status == "succeeded"
    assert cap1.http_status == 200
    assert len(cap1.sha256) == 64

    # Extract and persist initial evidence
    raw_payload1 = {
        "actor_a": "GhostVendor",
        "actor_b": "Nightshade99",
        "evidence": "PGP Fingerprint: 1122 33AA BBCC DD44 5566 7788 99EE FF00 1234 5678; Wallet Address: 3GhostVendorFakeWallet000000000000",
        "capture_id": cap1.capture_id,
        "source_url": cap1.url,
    }
    initial_units = adapter.extract(raw_payload1)
    assert len(initial_units) == 2
    for u in initial_units:
        evidence_repo.save(u)

    assert evidence_repo.count() == 2

    # -------------------------------------------------------------
    # 2. Offline: Source goes down / returns HTTP 503
    # -------------------------------------------------------------
    cap2, content2 = replayer.fetch_fixture("fixture://market-a/ghostvendor_offline.html")
    assert cap2.status == "failed"
    assert cap2.http_status == 503
    assert b"503 Service Temporarily Unavailable" in content2
    assert "503" in cap2.not_collected_reason

    # CRUCIAL EC-01 REQUIREMENT:
    # Prior evidence MUST NOT be deleted or marked invalid simply because the source went offline.
    prior_evidence = evidence_repo.list_by_pair("GhostVendor", "Nightshade99")
    assert len(prior_evidence) == 2
    assert prior_evidence[0].capture_id == cap1.capture_id

    # -------------------------------------------------------------
    # 3. Changed Content: Source recovers with updated content
    # -------------------------------------------------------------
    cap3, content3 = replayer.fetch_fixture("fixture://market-a/ghostvendor_changed.html")
    assert cap3.status == "succeeded"
    assert cap3.http_status == 200
    # Content has changed, so checksums must differ
    assert cap3.sha256 != cap1.sha256

    # -------------------------------------------------------------
    # 4. Audit and Provenance Verification:
    # All 3 transition captures are durably cataloged in repository
    # -------------------------------------------------------------
    all_captures = replayer.capture_manager.capture_repo.list_by_source("market-a")
    assert len(all_captures) == 3

    statuses = [c["status"] for c in all_captures]
    assert "succeeded" in statuses
    assert "failed" in statuses
