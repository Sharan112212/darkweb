from adapters.behavior_adapter import BehaviorAdapter
from fusion.explainable_fusion import ExplainableFusionEngine
from db.repositories.evidence_repo import EvidenceRepository
from db.repositories.link_repo import LinkRepository

def test_branch7_end_to_end_behavior_pipeline(temp_db):
    evidence_repo = EvidenceRepository(temp_db)
    link_repo = LinkRepository(temp_db)

    posts_ghost = [
        {"content": "yo fam quality checked twice definately worth the wait", "created_at": "2026-08-01T14:00:00Z"},
        {"content": "new security tool release quality checked twice", "created_at": "2026-08-05T14:30:00Z"}
    ]
    posts_night = [
        {"content": "yo fam quality checked twice definately worth the wait", "created_at": "2026-09-01T14:05:00Z"},
        {"content": "updated security tool release quality checked twice", "created_at": "2026-09-05T14:25:00Z"}
    ]

    # 1. Behavior Extraction & Adapter
    adapter = BehaviorAdapter()
    units = adapter.extract({
        "actor_a": "actor_ghostvendor",
        "posts_a": posts_ghost,
        "actor_b": "actor_nightshade99",
        "posts_b": posts_night
    })

    assert len(units) > 0

    # 2. Persist Evidence to DB
    for u in units:
        evidence_repo.save(u)

    # 3. Run Fusion Engine
    fusion = ExplainableFusionEngine()
    candidate_link = fusion.evaluate_pair(
        left_entity_id="actor_ghostvendor",
        right_entity_id="actor_nightshade99",
        evidence_units=units
    )

    # 4. Enforce Category B caps (Behavioral contribution capped <= 0.65 => tier <= possible_association)
    assert candidate_link.score <= 0.70
    assert candidate_link.tier in ["possible_association", "unresolved"]

    # 5. Persist Candidate Link to DB
    saved = link_repo.save_candidate_link(candidate_link)
    saved_link_id = saved["link_id"] if isinstance(saved, dict) else saved.link_id
    assert saved_link_id == candidate_link.link_id
