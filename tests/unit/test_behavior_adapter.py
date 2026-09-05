import pytest
from adapters.behavior_adapter import BehaviorAdapter
from models.enums import IndicatorType

def test_behavior_adapter_extract():
    adapter = BehaviorAdapter()

    posts_a = [
        {"content": "yo fam quality checked twice definately worth the wait", "created_at": "2026-09-01T14:00:00Z"},
        {"content": "new release quality checked twice", "created_at": "2026-09-02T14:15:00Z"}
    ]
    posts_b = [
        {"content": "yo fam quality checked twice definately worth the wait", "created_at": "2026-09-03T14:10:00Z"},
        {"content": "new tools quality checked twice", "created_at": "2026-09-04T14:20:00Z"}
    ]

    units = adapter.extract({"actor_a": "GhostVendor", "posts_a": posts_a, "actor_b": "Nightshade99", "posts_b": posts_b})
    assert len(units) > 0

    for u in units:
        assert u.category == "B"
        assert u.source == "behavior_engine"
        assert any("Category B maximum contribution capped" in lim for lim in u.limitations)
        assert u.independence_group_id.startswith("indep_behavior_")

    types = [u.indicator_type for u in units]
    assert IndicatorType.persona_migration_candidate.value in types
