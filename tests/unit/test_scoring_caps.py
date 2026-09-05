"""
Unit tests for scoring caps and defensive guardrails in ExplainableFusionEngine.
Tests:
- Category S ceiling (≤ 0.20 max contribution, regardless of linguistic confidence or volume).
- Text-only / Behavior-only cap (when K=0 and I=0, score ≤ 0.65, preventing likely_same_actor).
- Infrastructure-alone cap (Category I ≤ 0.65).
- Uncapped cryptographic signals (Category K reaching high confidence tiers).
"""
import pytest
from fusion.explainable_fusion import ExplainableFusionEngine
from models.enums import IndicatorType, Tier
from models.evidence import EvidenceUnit


def _create_unit(
    evidence_id: str,
    indicator_type: str,
    weight: float,
    independence_group_id: str,
    entities: list = None,
) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=evidence_id,
        capture_id="cap_cap_001",
        source="market_test",
        source_version="1.0.0",
        indicator_type=indicator_type,
        indicator_value="test_val",
        linked_entities=entities or ["PersonaA", "PersonaB"],
        confidence_weight=weight,
        captured_at="2026-09-05T12:00:00Z",
        source_url="http://test.onion",
        raw_evidence_hash="sha256:caphash123",
        raw_evidence_reference="fixtures/test.html",
        independence_group_id=independence_group_id,
        explanation=f"Testing cap on {indicator_type}",
    )


# ==============================================================================
# 1. Category S Cap (≤ 0.20)
# ==============================================================================

def test_category_s_single_high_weight_is_capped_at_0_20():
    """Single semantic similarity unit with weight 0.85 must be capped at 0.20."""
    engine = ExplainableFusionEngine()
    unit = _create_unit("ev_s_1", IndicatorType.semantic_similarity.value, 0.85, "grp_s_1")

    link = engine.evaluate_pair("PersonaA", "PersonaB", [unit])

    assert link.category_breakdown["S"]["score"] == 0.20
    assert link.score == 0.20
    assert link.tier in [Tier.insufficient_evidence.value, Tier.unresolved.value]


def test_category_s_multiple_independent_signals_never_exceed_0_20():
    """
    Multiple independent stylometric and semantic units (e.g. cosine 0.90, 0.85, 0.80)
    would mathematically accumulate to >0.99 under Noisy-OR, but MUST be strictly capped at 0.20.
    """
    engine = ExplainableFusionEngine()
    units = [
        _create_unit("ev_s_1", IndicatorType.semantic_similarity.value, 0.90, "grp_s_1"),
        _create_unit("ev_s_2", IndicatorType.classical_stylometry.value, 0.85, "grp_s_2"),
        _create_unit("ev_s_3", IndicatorType.semantic_similarity.value, 0.80, "grp_s_3"),
    ]

    link = engine.evaluate_pair("PersonaA", "PersonaB", units)

    assert link.category_breakdown["S"]["score"] == 0.20
    assert link.score <= 0.20
    assert link.tier != Tier.possible_association.value
    assert link.tier != Tier.likely_same_actor.value
    assert link.tier != Tier.observed_technical_identity.value


# ==============================================================================
# 2. Text-Only and Behavior-Only Cap (≤ 0.65, Cannot Reach likely_same_actor)
# ==============================================================================

def test_text_and_behavior_only_cannot_reach_likely_same_actor():
    """
    When K=0 and I=0 (no cryptographic and no infrastructure signals),
    even an overwhelming combination of Behavioral (Category B: cap 0.65) and
    Stylometric (Category S: cap 0.20) signals would produce raw fused score:
    1 - (1 - 0.65) * (1 - 0.20) = 1 - (0.35 * 0.80) = 1 - 0.28 = 0.72.
    Under the text/behavior guardrail, it MUST be capped at 0.65 and CANNOT reach
    likely_same_actor (which starts at 0.70).
    """
    engine = ExplainableFusionEngine()

    # Create multiple independent Category B signals to saturate Category B to 0.65
    units = [
        _create_unit("ev_b_1", IndicatorType.posting_time_pattern.value, 0.50, "grp_b_1"),
        _create_unit("ev_b_2", IndicatorType.vocabulary_overlap.value, 0.50, "grp_b_2"),
        _create_unit("ev_b_3", IndicatorType.template_match.value, 0.50, "grp_b_3"),
        _create_unit("ev_b_4", IndicatorType.persona_migration_candidate.value, 0.50, "grp_b_4"),
        # And Category S
        _create_unit("ev_s_1", IndicatorType.semantic_similarity.value, 0.80, "grp_s_1"),
    ]

    link = engine.evaluate_pair("PersonaA", "PersonaB", units)

    # Category B capped at 0.65, Category S capped at 0.20
    assert link.category_breakdown["B"]["score"] == 0.65
    assert link.category_breakdown["S"]["score"] == 0.20
    assert link.category_breakdown["K"]["score"] == 0.0
    assert link.category_breakdown["I"]["score"] == 0.0

    # Final score MUST be capped at 0.65
    assert link.score == 0.65
    # Tier must be possible_association, NOT likely_same_actor
    assert link.tier == Tier.possible_association.value
    assert link.tier != Tier.likely_same_actor.value


def test_text_only_alone_bounded():
    """Only Category S evidence without any other signals is bounded at 0.20."""
    engine = ExplainableFusionEngine()
    unit = _create_unit("ev_s_only", IndicatorType.semantic_similarity.value, 0.95, "grp_s")

    link = engine.evaluate_pair("PersonaA", "PersonaB", [unit])
    assert link.score <= 0.20
    assert link.tier in [Tier.insufficient_evidence.value, Tier.unresolved.value]


# ==============================================================================
# 3. Infrastructure-Alone Cap (Category I ≤ 0.65)
# ==============================================================================

def test_infrastructure_alone_capped_at_0_65():
    """
    Multiple independent infrastructure signals alone saturate Category I at 0.65.
    Without K, infrastructure alone cannot reach likely_same_actor (≥ 0.70).
    """
    engine = ExplainableFusionEngine()
    units = [
        _create_unit("ev_i_1", IndicatorType.certificate_fingerprint.value, 0.77, "grp_i_1"),
        _create_unit("ev_i_2", IndicatorType.onionscan_ssh_key.value, 0.75, "grp_i_2"),
        _create_unit("ev_i_3", IndicatorType.onionscan_analytics_id.value, 0.65, "grp_i_3"),
    ]

    link = engine.evaluate_pair("PersonaA", "PersonaB", units)
    assert link.category_breakdown["I"]["score"] == 0.65
    assert link.score == 0.65
    assert link.tier == Tier.possible_association.value


# ==============================================================================
# 4. Uncapped Cryptographic Signals
# ==============================================================================

def test_cryptographic_signals_reach_highest_tiers():
    """
    Unlike S, B, and I, Category K is uncapped (max_contribution = 1.00)
    and can independently elevate a link to observed_technical_identity (≥ 0.90).
    """
    engine = ExplainableFusionEngine()
    unit = _create_unit("ev_k_pgp", IndicatorType.pgp_fingerprint.value, 0.95, "grp_k")

    link = engine.evaluate_pair("PersonaA", "PersonaB", [unit])
    assert link.category_breakdown["K"]["score"] == 0.95
    assert link.score == 0.95
    assert link.tier == Tier.observed_technical_identity.value
