import sqlite3
import tempfile
import os
from adapters.legacy_fusion_adapter import LegacyFusionAdapter
from models.evidence import EvidenceUnit


def test_legacy_fusion_adapter_conversion():
    # 1. PGP EvidenceUnit (Category K) -> shared_identifier
    pgp_unit = EvidenceUnit(
        evidence_id="ev_pgp_test",
        schema_version="1.0.0",
        category="K",
        capture_id="cap_001",
        source="identity_graph",
        source_version="1.0.0",
        indicator_type="pgp_fingerprint",
        indicator_value="9A3F21B477C0EE125D6A8F9011C34B22FA019D77",
        linked_entities=["DarkFox_v2", "DarkFox"],
        confidence_weight=0.95,
        captured_at="2026-09-05T10:00:00Z",
        source_url="identity://DarkFox/DarkFox_v2",
        raw_evidence_hash="hash123",
        raw_evidence_reference="ref123",
        independence_group_id="indep_pgp_123",
        explanation="Shared PGP fingerprint: 9A3F21B477C0EE125D6A8F9011C34B22FA019D77",
    )

    tup = LegacyFusionAdapter.to_legacy_link(pgp_unit)
    assert tup[0] == "DarkFox"  # min
    assert tup[1] == "DarkFox_v2"  # max
    assert tup[2] == "shared_identifier"
    assert tup[3] == pgp_unit.explanation
    assert tup[4] == 95

    # 2. Semantic EvidenceUnit (Category S) -> stylometric
    sem_unit = EvidenceUnit(
        evidence_id="ev_sem_test",
        schema_version="1.0.0",
        category="S",
        capture_id="cap_002",
        source="minilm_stylometry",
        source_version="1.0.0",
        indicator_type="semantic_similarity",
        indicator_value="similarity_0.8500",
        linked_entities=["Nightshade99", "GhostVendor"],
        confidence_weight=0.72,
        captured_at="2026-09-05T10:00:00Z",
        source_url="semantic://GhostVendor/Nightshade99",
        raw_evidence_hash="hash456",
        raw_evidence_reference="ref456",
        independence_group_id="indep_sem_123",
        explanation="Writing style similarity: 0.8500",
    )

    tup_sem = LegacyFusionAdapter.to_legacy_link(sem_unit)
    assert tup_sem[0] == "GhostVendor"
    assert tup_sem[1] == "Nightshade99"
    assert tup_sem[2] == "stylometric"
    assert tup_sem[4] == 72

    # Dictionary representation
    d = LegacyFusionAdapter.to_legacy_dict(sem_unit)
    assert d["actor_a"] == "GhostVendor"
    assert d["actor_b"] == "Nightshade99"
    assert d["link_type"] == "stylometric"
    assert d["confidence_score"] == 72


def test_legacy_fusion_adapter_write_to_db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        unit = EvidenceUnit(
            evidence_id="ev_db_test",
            schema_version="1.0.0",
            category="K",
            capture_id="cap_003",
            source="identity_graph",
            source_version="1.0.0",
            indicator_type="wallet_address",
            indicator_value="bc1qzp3d8x9k2m4h7j6n5w0e1r2t3y4u5i6o7p8a9",
            linked_entities=["DarkFox", "DarkFox_v2"],
            confidence_weight=0.90,
            captured_at="2026-09-05T10:00:00Z",
            source_url="identity://DarkFox/DarkFox_v2",
            raw_evidence_hash="hash789",
            raw_evidence_reference="ref789",
            independence_group_id="indep_wallet_123",
            explanation="Shared wallet address",
        )

        LegacyFusionAdapter.write_to_db([unit], db_path=db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT actor_a, actor_b, link_type, evidence, confidence_score FROM relationship_links")
        rows = cur.fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0] == ("DarkFox", "DarkFox_v2", "shared_identifier", "Shared wallet address", 90)
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
