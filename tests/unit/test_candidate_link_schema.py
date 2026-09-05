import pytest
from pydantic import ValidationError
from models.candidate_link import CandidateLink

def test_valid_candidate_link():
    link = CandidateLink(
        link_id="lnk_test_001",
        link_version=1,
        left_entity_id="DarkFox",
        right_entity_id="DarkFox_v2",
        state="proposed",
        score=0.99,
        tier="observed_technical_identity",
        score_status="observed",
        category_breakdown={
            "K": {"score": 0.95, "state": "observed", "evidence_ids": ["ev_pgp_1"]},
            "I": {"score": 0.0, "state": "not_available", "evidence_ids": []},
            "B": {"score": 0.0, "state": "not_available", "evidence_ids": []},
            "S": {"score": 0.79, "state": "observed", "evidence_ids": ["ev_sbert_1"]}
        },
        evidence_ids=["ev_pgp_1", "ev_sbert_1"],
        explanation="Association boosted by PGP fingerprint match and semantic similarity.",
        limitations=["Text evidence is supporting only."],
        score_model_version="scoring-v1.0",
        calculation_input_hash="sha256:testinputhash123",
        created_at="2026-09-05T10:00:00Z",
        updated_at="2026-09-05T10:00:00Z"
    )
    assert link.link_id == "lnk_test_001"
    assert link.score == 0.99
    assert link.tier == "observed_technical_identity"

def test_invalid_score_range():
    with pytest.raises(ValidationError):
        CandidateLink(
            link_id="lnk_invalid",
            left_entity_id="A",
            right_entity_id="B",
            score=-0.5, # Out of range
            tier="insufficient_evidence",
            explanation="Invalid score test",
            calculation_input_hash="hash",
            created_at="now",
            updated_at="now"
        )
