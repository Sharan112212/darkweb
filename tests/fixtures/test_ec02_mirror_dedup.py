"""
Fixture and edge-case test: EC-02 Mirror Deduplication.
Tests mirror page duplicate content assignment of identical independence_group_id.
Ensures duplicate/mirrored observations cannot artificially inflate confidence scores in fusion.
"""
from collection.fixture_replayer import FixtureReplayer
from collection.normalizer import CollectionNormalizer
from adapters.identity_evidence_adapter import IdentityEvidenceAdapter


def test_ec02_mirror_dedup_independence_group_assignment(temp_db):
    """
    EC-02: Mirrors/reposts/duplicate jobs.
    Required control: Content hash + independence group + idempotency.
    Mirrored pages with identical technical indicators must receive identical independence_group_id.
    """
    replayer = FixtureReplayer(db_path=temp_db)
    normalizer = CollectionNormalizer()
    adapter = IdentityEvidenceAdapter()

    # 1. Fetch original profile from Market A
    cap1, content1 = replayer.fetch_fixture("fixture://market-a/ghostvendor.html")
    assert cap1.status == "succeeded"

    # 2. Fetch mirror/repost profile from Market B
    cap2, content2 = replayer.fetch_fixture("fixture://market-b/mirror_ghostvendor.html")
    assert cap2.status == "succeeded"

    # Verify these are distinct capture events across different sources
    assert cap1.capture_id != cap2.capture_id
    assert cap1.source_id == "market-a"
    assert cap2.source_id == "market-b"

    # 3. Extract evidence units from both pages
    # Both pages share the same synthetic PGP fingerprint and wallet address
    payload_original = {
        "actor_a": "GhostVendor",
        "actor_b": "GhostVendor_Mirror",
        "evidence": "PGP Fingerprint: 1122 33AA BBCC DD44 5566 7788 99EE FF00 1234 5678; Wallet Address: 3GhostVendorFakeWallet000000000000",
        "capture_id": cap1.capture_id,
        "source_url": cap1.url,
        "source": "market-a",
    }
    payload_mirror = {
        "actor_a": "GhostVendor",
        "actor_b": "GhostVendor_Mirror",
        "evidence": "PGP Fingerprint: 1122 33AA BBCC DD44 5566 7788 99EE FF00 1234 5678; Wallet Address: 3GhostVendorFakeWallet000000000000",
        "capture_id": cap2.capture_id,
        "source_url": cap2.url,
        "source": "market-b",
    }

    units_original = adapter.extract(payload_original)
    units_mirror = adapter.extract(payload_mirror)

    assert len(units_original) == 2
    assert len(units_mirror) == 2

    # 4. CRUCIAL EC-02 ASSERTION:
    # Mirrored observations of the same indicator MUST receive IDENTICAL independence_group_id
    pgp_orig = next(u for u in units_original if u.indicator_type == "pgp_fingerprint")
    pgp_mirror = next(u for u in units_mirror if u.indicator_type == "pgp_fingerprint")
    assert pgp_orig.independence_group_id == pgp_mirror.independence_group_id
    assert pgp_orig.independence_group_id.startswith("indep_pgp_")

    wallet_orig = next(u for u in units_original if u.indicator_type == "wallet_address")
    wallet_mirror = next(u for u in units_mirror if u.indicator_type == "wallet_address")
    assert wallet_orig.independence_group_id == wallet_mirror.independence_group_id
    assert wallet_orig.independence_group_id.startswith("indep_wallet_")

    # 5. Normalizer content-level independence group calculation
    indep_id_1 = normalizer.compute_independence_group_id(
        content=content1,
        indicator_value="112233AABBCCDD445566778899EEFF0012345678",
    )
    indep_id_2 = normalizer.compute_independence_group_id(
        content=content2,
        indicator_value="112233AABBCCDD445566778899EEFF0012345678",
    )
    assert indep_id_1 == indep_id_2
    assert indep_id_1.startswith("indep_")
