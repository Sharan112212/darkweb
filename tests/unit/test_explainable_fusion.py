"""
Unit tests for ExplainableFusionEngine.
Tests:
- Noisy-OR mathematical calculations (single weight, multiple weights, empty, boundary conditions).
- Multi-signal boost (corroborating independent categories elevates score beyond single signal).
- Deterministic calculation_input_hash (order-invariance, collision-resistance, audit integrity).
- Entity pair ordering normalization (alphabetical min/max).
- Independence group deduplication per EC-24 (mirrors/duplicates do not inflate scores).
"""
import hashlib
import pytest
from fusion.explainable_fusion import ExplainableFusionEngine
from models.enums import IndicatorType, Tier, ScoreStatus, LinkState
from models.evidence import EvidenceUnit


def _create_test_unit(
    evidence_id: str,
    indicator_type: str,
    weight: float,
    independence_group_id: str,
    entities: list = None,
    limitations: list = None,
) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=evidence_id,
        capture_id="cap_test_001",
        source="market_a",
        source_version="1.0.0",
        indicator_type=indicator_type,
        indicator_value="val_test",
        linked_entities=entities or ["ViperX", "ViperX_Reborn"],
        confidence_weight=weight,
        captured_at="2026-09-05T12:00:00Z",
        source_url="http://market.onion/listing",
        raw_evidence_hash="sha256:test123hash",
        raw_evidence_reference="fixtures/market.html",
        independence_group_id=independence_group_id,
        explanation=f"Test evidence for {indicator_type}",
        limitations=limitations or ["Observed in synthetic test fixture."],
    )


# ==============================================================================
# 1. Noisy-OR Mathematical Calculations
# ==============================================================================

def test_noisy_or_empty_list():
    """Empty weights list must return 0.0."""
    engine = ExplainableFusionEngine()
    assert engine.calculate_noisy_or([]) == 0.0


def test_noisy_or_single_weight():
    """Single weight must return that exact weight."""
    engine = ExplainableFusionEngine()
    assert engine.calculate_noisy_or([0.75]) == 0.75
    assert engine.calculate_noisy_or([0.90]) == 0.90
    assert engine.calculate_noisy_or([0.0]) == 0.0


def test_noisy_or_multiple_independent_weights():
    """
    Two independent 0.50 signals: 1 - (1 - 0.5) * (1 - 0.5) = 1 - 0.25 = 0.75.
    Three independent 0.50 signals: 1 - (0.5)^3 = 0.875.
    """
    engine = ExplainableFusionEngine()
    assert engine.calculate_noisy_or([0.5, 0.5]) == 0.75
    assert engine.calculate_noisy_or([0.5, 0.5, 0.5]) == 0.875


def test_noisy_or_high_confidence_combination():
    """
    ViperX benchmark math:
    Signal A: 0.90, Signal B: 0.18
    1 - (1 - 0.90) * (1 - 0.18) = 1 - (0.10 * 0.82) = 1 - 0.082 = 0.9180.
    """
    engine = ExplainableFusionEngine()
    score = engine.calculate_noisy_or([0.90, 0.18])
    assert score == 0.918


# ==============================================================================
# 2. Multi-Signal Boost
# ==============================================================================

def test_multi_signal_boost_elevates_confidence_tier():
    """
    Test that combining a Cryptographic (K: wallet 0.90) signal and a Semantic (S: 0.18)
    signal results in a multi-signal boost exceeding 0.90 into observed_technical_identity.
    """
    engine = ExplainableFusionEngine()

    u_wallet = _create_test_unit(
        evidence_id="ev_btc_01",
        indicator_type=IndicatorType.wallet_address.value,
        weight=0.90,
        independence_group_id="indep_wallet_01",
    )
    u_sbert = _create_test_unit(
        evidence_id="ev_sbert_01",
        indicator_type=IndicatorType.semantic_similarity.value,
        weight=0.18,
        independence_group_id="indep_sbert_01",
    )

    link = engine.evaluate_pair("ViperX", "ViperX_Reborn", [u_wallet, u_sbert])

    # Fused score must be strictly higher than individual signals
    assert link.score > 0.90
    assert link.score == pytest.approx(0.918, abs=0.001)
    assert link.tier == Tier.observed_technical_identity.value
    assert link.category_breakdown["K"]["score"] == 0.90
    assert link.category_breakdown["S"]["score"] == 0.18
    assert link.category_breakdown["K"]["state"] == "observed"
    assert link.category_breakdown["S"]["state"] == "observed"
    assert link.category_breakdown["I"]["state"] == "not_available"
    assert link.category_breakdown["B"]["state"] == "not_available"


def test_multi_signal_cross_category_infra_and_behavior():
    """
    Combining Infrastructure (I: cert 0.60) and Behavioral (B: posting time 0.50)
    yields: 1 - (1 - 0.60)*(1 - 0.50) = 1 - (0.40 * 0.50) = 0.80.
    Since I > 0, text-only cap does not apply. Tier reaches likely_same_actor.
    """
    engine = ExplainableFusionEngine()

    u_infra = _create_test_unit(
        evidence_id="ev_cert_01",
        indicator_type=IndicatorType.certificate_fingerprint.value,
        weight=0.60,
        independence_group_id="indep_cert_01",
    )
    u_time = _create_test_unit(
        evidence_id="ev_time_01",
        indicator_type=IndicatorType.posting_time_pattern.value,
        weight=0.50,
        independence_group_id="indep_time_01",
    )

    link = engine.evaluate_pair("ActorA", "ActorB", [u_infra, u_time])
    assert link.score == pytest.approx(0.80, abs=0.001)
    assert link.tier == Tier.likely_same_actor.value


# ==============================================================================
# 3. Calculation Input Hash & Audit Determinism
# ==============================================================================

def test_calculation_input_hash_format_and_reproducibility():
    """Verify input hash is a valid sha256 formatted string and reproducible."""
    engine = ExplainableFusionEngine()

    u1 = _create_test_unit("ev_001", IndicatorType.alias.value, 0.60, "grp_1")
    u2 = _create_test_unit("ev_002", IndicatorType.vocabulary_overlap.value, 0.40, "grp_2")

    link = engine.evaluate_pair("ActorA", "ActorB", [u1, u2])

    assert link.calculation_input_hash.startswith("sha256:")
    assert len(link.calculation_input_hash) == 71  # "sha256:" (7) + 64 hex chars


def test_calculation_input_hash_order_invariance():
    """Reversing the evidence list must yield the exact same calculation_input_hash."""
    engine = ExplainableFusionEngine()

    u1 = _create_test_unit("ev_alpha", IndicatorType.alias.value, 0.60, "grp_1")
    u2 = _create_test_unit("ev_beta", IndicatorType.vocabulary_overlap.value, 0.40, "grp_2")

    link_forward = engine.evaluate_pair("ActorA", "ActorB", [u1, u2])
    link_reverse = engine.evaluate_pair("ActorA", "ActorB", [u2, u1])

    assert link_forward.calculation_input_hash == link_reverse.calculation_input_hash
    assert link_forward.score == link_reverse.score


def test_calculation_input_hash_sensitivity():
    """Adding or modifying an evidence unit must change the calculation_input_hash."""
    engine = ExplainableFusionEngine()

    u1 = _create_test_unit("ev_001", IndicatorType.alias.value, 0.60, "grp_1")
    u2 = _create_test_unit("ev_002", IndicatorType.vocabulary_overlap.value, 0.40, "grp_2")
    u3 = _create_test_unit("ev_003", IndicatorType.template_match.value, 0.30, "grp_3")

    link_two = engine.evaluate_pair("ActorA", "ActorB", [u1, u2])
    link_three = engine.evaluate_pair("ActorA", "ActorB", [u1, u2, u3])

    assert link_two.calculation_input_hash != link_three.calculation_input_hash


# ==============================================================================
# 4. Entity Pair Ordering Normalization
# ==============================================================================

def test_entity_pair_ordering_normalized():
    """evaluate_pair must normalize entities so left <= right alphabetically."""
    engine = ExplainableFusionEngine()

    u1 = _create_test_unit("ev_001", IndicatorType.alias.value, 0.60, "grp_1", entities=["Zeta", "Alpha"])

    link_za = engine.evaluate_pair("Zeta", "Alpha", [u1])
    assert link_za.left_entity_id == "Alpha"
    assert link_za.right_entity_id == "Zeta"

    link_az = engine.evaluate_pair("Alpha", "Zeta", [u1])
    assert link_az.left_entity_id == "Alpha"
    assert link_az.right_entity_id == "Zeta"


# ==============================================================================
# 5. Independence Group Deduplication (EC-24)
# ==============================================================================

def test_independence_group_deduplication_prevents_inflation():
    """
    EC-24: Multiple observations sharing the SAME independence_group_id must not
    inflate Noisy-OR. Only the max weight within that independence group contributes.
    """
    engine = ExplainableFusionEngine()

    # Three mirrored scrapes of the exact same PGP key (same independence group)
    u_mirror1 = _create_test_unit("ev_pgp_1", IndicatorType.pgp_fingerprint.value, 0.95, "indep_mirror_site_hash_123")
    u_mirror2 = _create_test_unit("ev_pgp_2", IndicatorType.pgp_fingerprint.value, 0.95, "indep_mirror_site_hash_123")
    u_mirror3 = _create_test_unit("ev_pgp_3", IndicatorType.pgp_fingerprint.value, 0.90, "indep_mirror_site_hash_123")

    link = engine.evaluate_pair("ActorA", "ActorB", [u_mirror1, u_mirror2, u_mirror3])

    # Score must be exactly 0.95 (max weight of group), NOT 1 - (0.05)^2 * (0.10) = 0.99975
    assert link.score == 0.95
    assert link.category_breakdown["K"]["score"] == 0.95
    assert len(link.evidence_ids) == 3


def test_independent_groups_accumulate():
    """
    Signals with DIFFERENT independence_group_ids must combine via Noisy-OR.
    """
    engine = ExplainableFusionEngine()

    # Two distinct observations with different independence groups
    u_pgp = _create_test_unit("ev_pgp_01", IndicatorType.pgp_fingerprint.value, 0.95, "indep_pgp_source_a")
    u_wallet = _create_test_unit("ev_wallet_01", IndicatorType.wallet_address.value, 0.90, "indep_wallet_source_b")

    link = engine.evaluate_pair("ActorA", "ActorB", [u_pgp, u_wallet])

    # 1 - (1 - 0.95)*(1 - 0.90) = 1 - (0.05 * 0.10) = 1 - 0.005 = 0.995
    assert link.score == pytest.approx(0.995, abs=0.001)
    assert link.tier == Tier.observed_technical_identity.value
