import pytest
from analysis.behavior_engine import BehaviorEngine

def test_posting_time_histogram_and_similarity():
    engine = BehaviorEngine()

    posts_a = [
        {"created_at": "2026-09-01T14:00:00Z"},
        {"created_at": "2026-09-02T14:30:00Z"},
        {"created_at": "2026-09-03T15:00:00Z"},
    ]
    posts_b = [
        {"created_at": "2026-09-04T14:15:00Z"},
        {"created_at": "2026-09-05T14:45:00Z"},
        {"created_at": "2026-09-06T15:15:00Z"},
    ]

    hist_a = engine.compute_posting_time_histogram(posts_a)
    assert len(hist_a) == 24
    assert hist_a[14] > 0.0

    sim = engine.compute_posting_time_similarity(posts_a, posts_b)
    assert sim >= 0.90  # Both peak around 14:00-15:00 UTC

def test_vocabulary_overlap():
    engine = BehaviorEngine()
    posts_a = [{"content": "Selling high quality security software and exploit tools"}]
    posts_b = [{"content": "High quality security tools available for instant delivery"}]

    sim = engine.compute_vocabulary_overlap(posts_a, posts_b)
    assert sim > 0.30

def test_template_matching():
    engine = BehaviorEngine()
    posts_a = [{"content": "yo fam quality checked twice definately worth the wait"}]
    posts_b = [{"content": "yo fam quality checked twice definately worth the wait"}]

    score, phrases = engine.compute_template_matches(posts_a, posts_b)
    assert score >= 0.80
    assert len(phrases) > 0

def test_analyze_migration_contextual_gate_failure():
    engine = BehaviorEngine()
    # Unrelated posts with no contextual signals
    posts_a = [{"content": "Selling apples and oranges"}]
    posts_b = [{"content": "Database administration and SQL queries"}]

    res = engine.analyze_migration("actor_a", posts_a, "actor_b", posts_b)
    assert res["is_candidate"] is False
    assert res["has_contextual_signal"] is False
    assert "Failed contextual signal gate" in res["reason"]
