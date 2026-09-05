from fusion.explanation_builder import ExplanationBuilder
from models.evidence import EvidenceUnit


def test_explanation_builder_basic():
    u1 = EvidenceUnit(
        evidence_id="ev_pgp_1",
        capture_id="c1",
        source="forum",
        source_version="1",
        indicator_type="pgp_fingerprint",
        indicator_value="9A3F",
        linked_entities=["ActorA", "ActorB"],
        confidence_weight=0.95,
        captured_at="2026-09-01T00:00:00Z",
        source_url="http://example.onion",
        raw_evidence_hash="h1",
        raw_evidence_reference="r1",
        independence_group_id="grp_1",
        explanation="PGP key match",
        limitations=["Key self-published without third-party signature."],
    )
    u2 = EvidenceUnit(
        evidence_id="ev_sem_1",
        capture_id="c1",
        source="forum",
        source_version="1",
        indicator_type="semantic_similarity",
        indicator_value="0.88",
        linked_entities=["ActorA", "ActorB"],
        confidence_weight=0.15,
        captured_at="2026-09-01T00:00:00Z",
        source_url="http://example.onion",
        raw_evidence_hash="h2",
        raw_evidence_reference="r2",
        independence_group_id="grp_2",
        explanation="Semantic similarity match",
        limitations=["Key self-published without third-party signature."],  # duplicate limitation
    )

    category_breakdown = {
        "K": {"score": 0.95, "state": "observed", "evidence_ids": ["ev_pgp_1"]},
        "I": {"score": 0.0, "state": "not_available", "evidence_ids": []},
        "B": {"score": 0.0, "state": "not_available", "evidence_ids": []},
        "S": {"score": 0.15, "state": "observed", "evidence_ids": ["ev_sem_1"]},
    }

    explanation, limitations = ExplanationBuilder.build_explanation(
        evidence_units=[u1, u2],
        category_breakdown=category_breakdown,
        tier="observed_technical_identity",
        score=0.96,
    )

    assert "observed_technical_identity" in explanation
    assert "0.96" in explanation
    assert "Cryptographic & Hard Identifiers" in explanation
    assert "Semantic & Stylometric" in explanation
    assert "Total evidence units evaluated: 2" in explanation

    # Deduplication test: duplicate limitation should only appear once
    assert limitations.count("Key self-published without third-party signature.") == 1
    # Category S caveat should be appended
    assert any("Semantic and stylometric similarity is supporting evidence only" in lim for lim in limitations)


def test_explanation_builder_empty_evidence():
    explanation, limitations = ExplanationBuilder.build_explanation(
        evidence_units=[],
        category_breakdown={},
        tier="insufficient_evidence",
        score=0.0,
    )
    assert "insufficient_evidence" in explanation
    assert len(limitations) >= 1
    assert "All technical observations subject to analyst review." in limitations
