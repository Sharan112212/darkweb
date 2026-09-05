"""
Unit tests for CategoryClassifier.
Validates the classification of all 18 canonical IndicatorType enum values into K, I, B, S categories,
verifies set disjointness, total coverage, and fallback behavior for unmapped indicators.
"""
import pytest
from models.enums import IndicatorType
from models.evidence import EvidenceUnit
from fusion.category_classifier import CategoryClassifier


def _create_unit_with_type(indicator_type: str) -> EvidenceUnit:
    """Helper to build a valid EvidenceUnit for testing classification."""
    return EvidenceUnit(
        evidence_id=f"ev_test_{indicator_type}",
        capture_id="cap_test_001",
        source="test_source",
        source_version="1.0.0",
        indicator_type=indicator_type,
        indicator_value="val_test",
        linked_entities=["ActorA", "ActorB"],
        confidence_weight=0.85,
        captured_at="2026-09-05T12:00:00Z",
        source_url="http://test.onion/profile",
        raw_evidence_hash="sha256:abc123hash",
        raw_evidence_reference="fixtures/test.html",
        independence_group_id=f"indep_{indicator_type}",
        explanation=f"Testing {indicator_type}",
    )


def test_indicator_type_count():
    """Ensure exactly 18 indicator types are defined in IndicatorType enum."""
    assert len(IndicatorType) == 18, f"Expected 18 indicator types, found {len(IndicatorType)}"


def test_category_sets_are_disjoint_and_exhaustive():
    """Verify that K, I, B, S sets in CategoryClassifier are pairwise disjoint and cover all 18 types."""
    k_set = CategoryClassifier.K_TYPES
    i_set = CategoryClassifier.I_TYPES
    b_set = CategoryClassifier.B_TYPES
    s_set = CategoryClassifier.S_TYPES

    # Pairwise disjoint checks
    assert k_set.isdisjoint(i_set), f"K and I overlap on {k_set & i_set}"
    assert k_set.isdisjoint(b_set), f"K and B overlap on {k_set & b_set}"
    assert k_set.isdisjoint(s_set), f"K and S overlap on {k_set & s_set}"
    assert i_set.isdisjoint(b_set), f"I and B overlap on {i_set & b_set}"
    assert i_set.isdisjoint(s_set), f"I and S overlap on {i_set & s_set}"
    assert b_set.isdisjoint(s_set), f"B and S overlap on {b_set & s_set}"

    # Exhaustive coverage
    all_classified = k_set | i_set | b_set | s_set
    all_enums = {t.value for t in IndicatorType}
    assert all_classified == all_enums, f"Discrepancy: {all_classified ^ all_enums}"
    assert len(all_classified) == 18


@pytest.mark.parametrize(
    "indicator_type,expected_category",
    [
        # Category K: Cryptographic & Hard Identifiers (4 types)
        (IndicatorType.pgp_fingerprint.value, "K"),
        (IndicatorType.wallet_address.value, "K"),
        (IndicatorType.alias.value, "K"),
        (IndicatorType.contact_identifier.value, "K"),
        # Category I: Infrastructure (8 types)
        (IndicatorType.certificate_fingerprint.value, "I"),
        (IndicatorType.infrastructure_match.value, "I"),
        (IndicatorType.onionscan_analytics_id.value, "I"),
        (IndicatorType.onionscan_exif_leak.value, "I"),
        (IndicatorType.onionscan_server_status.value, "I"),
        (IndicatorType.onionscan_ssh_key.value, "I"),
        (IndicatorType.onionscan_certificate.value, "I"),
        (IndicatorType.onionscan_open_directory.value, "I"),
        # Category B: Behavioral (4 types)
        (IndicatorType.posting_time_pattern.value, "B"),
        (IndicatorType.vocabulary_overlap.value, "B"),
        (IndicatorType.template_match.value, "B"),
        (IndicatorType.persona_migration_candidate.value, "B"),
        # Category S: Semantic & Stylometric (2 types)
        (IndicatorType.semantic_similarity.value, "S"),
        (IndicatorType.classical_stylometry.value, "S"),
    ],
)
def test_all_18_indicator_types_classified_correctly(indicator_type, expected_category):
    """Test that each of the 18 indicator types is classified into its canonical category."""
    unit = _create_unit_with_type(indicator_type)
    category = CategoryClassifier.classify(unit)
    assert category == expected_category, (
        f"Indicator '{indicator_type}' classified as '{category}', expected '{expected_category}'"
    )


def test_unknown_indicator_type_fallback():
    """Verify fallback behavior for unknown/unregistered indicator types defaults to 'K'."""
    unit = _create_unit_with_type("unknown_future_indicator_type")
    assert CategoryClassifier.classify(unit) == "K"
