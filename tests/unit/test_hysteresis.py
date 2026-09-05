"""
Unit tests for tier boundary hysteresis margin (±0.03) per EC-25 in ExplainableFusionEngine.
Tests:
- Prevention of boundary flicker across all tier transitions:
  - 0.20 (insufficient_evidence <-> unresolved)
  - 0.40 (unresolved <-> possible_association)
  - 0.70 (possible_association <-> likely_same_actor)
  - 0.90 (likely_same_actor <-> observed_technical_identity)
- Threshold transition when delta strictly exceeds the 0.03 margin.
- Clean raw mapping when no previous link exists.
- CandidateLink version incrementing and creation timestamp preservation.
"""
from fusion.explainable_fusion import ExplainableFusionEngine
from models.candidate_link import CandidateLink
from models.enums import Tier, LinkState, ScoreStatus


def _create_candidate_link(score: float, tier: str, link_version: int = 1) -> CandidateLink:
    return CandidateLink(
        link_id="lnk_hysteresis_test",
        link_version=link_version,
        left_entity_id="ActorAlpha",
        right_entity_id="ActorBeta",
        state=LinkState.proposed.value,
        score=score,
        tier=tier,
        score_status=ScoreStatus.observed.value,
        category_breakdown={},
        evidence_ids=["ev_dummy"],
        explanation="Synthetic link for hysteresis boundary testing.",
        calculation_input_hash="sha256:dummyhash123",
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-01T00:00:00Z",
    )


# ==============================================================================
# 1. Initial Evaluation (No Previous Link)
# ==============================================================================

def test_initial_evaluation_maps_directly_without_hysteresis():
    """When previous_link is None, raw tier boundaries apply without delay."""
    engine = ExplainableFusionEngine()

    assert engine.map_score_to_tier(0.19, previous_link=None) == Tier.insufficient_evidence.value
    assert engine.map_score_to_tier(0.20, previous_link=None) == Tier.unresolved.value
    assert engine.map_score_to_tier(0.39, previous_link=None) == Tier.unresolved.value
    assert engine.map_score_to_tier(0.40, previous_link=None) == Tier.possible_association.value
    assert engine.map_score_to_tier(0.69, previous_link=None) == Tier.possible_association.value
    assert engine.map_score_to_tier(0.71, previous_link=None) == Tier.likely_same_actor.value
    assert engine.map_score_to_tier(0.89, previous_link=None) == Tier.likely_same_actor.value
    assert engine.map_score_to_tier(0.91, previous_link=None) == Tier.observed_technical_identity.value


# ==============================================================================
# 2. Boundary 0.70: possible_association <-> likely_same_actor
# ==============================================================================

def test_boundary_0_70_upgrade_within_margin_suppressed():
    """
    Previous tier: possible_association (score 0.68).
    New score: 0.71 (raw tier: likely_same_actor).
    Delta = 0.03 <= 0.03 margin.
    Must RETAIN possible_association.
    """
    engine = ExplainableFusionEngine()
    prev_link = _create_candidate_link(score=0.68, tier=Tier.possible_association.value)

    tier = engine.map_score_to_tier(0.71, previous_link=prev_link)
    assert tier == Tier.possible_association.value


def test_boundary_0_70_upgrade_exceeding_margin_transitions():
    """
    Previous tier: possible_association (score 0.68).
    New score: 0.74 (raw tier: likely_same_actor).
    Delta = 0.06 > 0.03 margin.
    Must UPGRADE to likely_same_actor.
    """
    engine = ExplainableFusionEngine()
    prev_link = _create_candidate_link(score=0.68, tier=Tier.possible_association.value)

    tier = engine.map_score_to_tier(0.74, previous_link=prev_link)
    assert tier == Tier.likely_same_actor.value


def test_boundary_0_70_downgrade_within_margin_suppressed():
    """
    Previous tier: likely_same_actor (score 0.72).
    New score: 0.69 (raw tier: possible_association).
    Delta = -0.03 <= 0.03 margin.
    Must RETAIN likely_same_actor.
    """
    engine = ExplainableFusionEngine()
    prev_link = _create_candidate_link(score=0.72, tier=Tier.likely_same_actor.value)

    tier = engine.map_score_to_tier(0.69, previous_link=prev_link)
    assert tier == Tier.likely_same_actor.value


def test_boundary_0_70_downgrade_exceeding_margin_transitions():
    """
    Previous tier: likely_same_actor (score 0.72).
    New score: 0.66 (raw tier: possible_association).
    Delta = -0.06 > 0.03 margin.
    Must DOWNGRADE to possible_association.
    """
    engine = ExplainableFusionEngine()
    prev_link = _create_candidate_link(score=0.72, tier=Tier.likely_same_actor.value)

    tier = engine.map_score_to_tier(0.66, previous_link=prev_link)
    assert tier == Tier.possible_association.value


# ==============================================================================
# 3. Boundary 0.40: unresolved <-> possible_association
# ==============================================================================

def test_boundary_0_40_upgrade_hysteresis():
    """
    Previous score: 0.39 (unresolved).
    New score: 0.41 (delta 0.02 <= 0.03) -> retains unresolved.
    New score: 0.45 (delta 0.06 > 0.03)  -> upgrades to possible_association.
    """
    engine = ExplainableFusionEngine()
    prev_link = _create_candidate_link(score=0.39, tier=Tier.unresolved.value)

    assert engine.map_score_to_tier(0.41, previous_link=prev_link) == Tier.unresolved.value
    assert engine.map_score_to_tier(0.45, previous_link=prev_link) == Tier.possible_association.value


# ==============================================================================
# 4. Boundary 0.90: likely_same_actor <-> observed_technical_identity
# ==============================================================================

def test_boundary_0_90_hysteresis():
    """
    Previous score: 0.89 (likely_same_actor).
    New score: 0.91 (delta 0.02 <= 0.03) -> retains likely_same_actor.
    New score: 0.95 (delta 0.06 > 0.03)  -> upgrades to observed_technical_identity.
    """
    engine = ExplainableFusionEngine()
    prev_link = _create_candidate_link(score=0.89, tier=Tier.likely_same_actor.value)

    assert engine.map_score_to_tier(0.91, previous_link=prev_link) == Tier.likely_same_actor.value
    assert engine.map_score_to_tier(0.95, previous_link=prev_link) == Tier.observed_technical_identity.value


# ==============================================================================
# 5. Boundary 0.20: insufficient_evidence <-> unresolved
# ==============================================================================

def test_boundary_0_20_hysteresis():
    """
    Previous score: 0.19 (insufficient_evidence).
    New score: 0.21 (delta 0.02 <= 0.03) -> retains insufficient_evidence.
    New score: 0.25 (delta 0.06 > 0.03)  -> upgrades to unresolved.
    """
    engine = ExplainableFusionEngine()
    prev_link = _create_candidate_link(score=0.19, tier=Tier.insufficient_evidence.value)

    assert engine.map_score_to_tier(0.21, previous_link=prev_link) == Tier.insufficient_evidence.value
    assert engine.map_score_to_tier(0.25, previous_link=prev_link) == Tier.unresolved.value


# ==============================================================================
# 6. Versioning & Timestamp Preservation on Re-evaluation
# ==============================================================================

def test_evaluate_pair_preserves_created_at_and_bumps_version():
    """
    When evaluating a pair with previous_link:
    - link_version must increment by 1.
    - created_at must match the original link created_at.
    - updated_at must be updated.
    """
    engine = ExplainableFusionEngine()
    from models.evidence import EvidenceUnit

    prev_link = _create_candidate_link(score=0.68, tier=Tier.possible_association.value, link_version=2)

    dummy_unit = EvidenceUnit(
        evidence_id="ev_update_1",
        capture_id="cap_update",
        source="market_a",
        source_version="1.0.0",
        indicator_type="alias",
        indicator_value="ActorAlpha",
        linked_entities=["ActorAlpha", "ActorBeta"],
        confidence_weight=0.71,
        captured_at="2026-09-05T12:00:00Z",
        source_url="http://test.onion",
        raw_evidence_hash="sha256:hash",
        raw_evidence_reference="fixtures/test.html",
        independence_group_id="grp_alias",
        explanation="Updated alias observation",
    )

    new_link = engine.evaluate_pair("ActorAlpha", "ActorBeta", [dummy_unit], previous_link=prev_link)

    assert new_link.link_version == 3
    assert new_link.created_at == prev_link.created_at
    assert new_link.updated_at != prev_link.created_at
