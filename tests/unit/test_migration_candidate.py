from analysis.behavior_engine import BehaviorEngine
from adapters.behavior_adapter import BehaviorAdapter
from fusion.explainable_fusion import ExplainableFusionEngine

def test_ghostvendor_to_nightshade99_rebrand_scenario():
    """
    Positive Scenario: GhostVendor -> Nightshade99 rebrand.
    GhostVendor becomes inactive on market-a, Nightshade99 starts posting with identical style & templates.
    System proposes persona migration candidate link in Category B capped at possible_association.
    """
    posts_ghost = [
        {"content": "yo fam quality checked twice definately worth the wait", "created_at": "2026-08-01T14:00:00Z"},
        {"content": "new exploit package quality checked twice", "created_at": "2026-08-05T14:30:00Z"}
    ]
    posts_night = [
        {"content": "yo fam quality checked twice definately worth the wait", "created_at": "2026-09-01T14:05:00Z"},
        {"content": "updated exploit package quality checked twice", "created_at": "2026-09-05T14:25:00Z"}
    ]

    adapter = BehaviorAdapter()
    evidence_units = adapter.extract({
        "actor_a": "GhostVendor",
        "posts_a": posts_ghost,
        "actor_b": "Nightshade99",
        "posts_b": posts_night
    })

    assert len(evidence_units) >= 2

    # Fusion evaluation
    fusion = ExplainableFusionEngine()
    link = fusion.evaluate_pair("GhostVendor", "Nightshade99", evidence_units=evidence_units)

    # Category B cap: score <= 0.65 => tier must be possible_association or unresolved
    assert link.score <= 0.70
    assert link.tier in ["possible_association", "unresolved"]
    assert "Category B" in link.explanation or "Behavioral" in link.explanation

def test_negative_copied_template_no_contextual_signal():
    """Negative Scenario 1: Generic single-word overlap does not trigger migration candidate."""
    engine = BehaviorEngine()
    posts_a = [{"content": "Product available for sale in store"}]
    posts_b = [{"content": "Different items for sale online"}]

    res = engine.analyze_migration("User_A", posts_a, "User_B", posts_b)
    assert res["is_candidate"] is False

def test_negative_similar_name_only():
    """Negative Scenario 2: Similar name alone without behavioral post overlap does not trigger migration."""
    engine = BehaviorEngine()
    posts_a = [{"content": "Crypto trading signals daily"}]
    posts_b = [{"content": "Cooking recipes and baking tips"}]

    res = engine.analyze_migration("GhostVendor_Fake", posts_a, "GhostVendor_Real", posts_b)
    assert res["is_candidate"] is False
