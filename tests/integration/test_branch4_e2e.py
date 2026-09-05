from scanners.onionscan_runner import OnionScanRunner
from adapters.infra_evidence_adapter import InfraEvidenceAdapter
from fusion.explainable_fusion import ExplainableFusionEngine
from db.repositories.evidence_repo import EvidenceRepository
from db.repositories.link_repo import LinkRepository

def test_branch4_end_to_end_pipeline(temp_db):
    # 1. Setup DB via temp_db fixture
    evidence_repo = EvidenceRepository(temp_db)
    link_repo = LinkRepository(temp_db)

    # 2. Run OnionScan for GhostVendor & Nightshade99
    runner = OnionScanRunner(mode="fixture_replay", fixtures_dir="fixtures/onionscan")
    units_ghost = runner.scan(target="ghostvendor.onion", target_entity="actor_ghostvendor")
    units_night = runner.scan(target="nightshade99.onion", target_entity="actor_nightshade99")

    assert len(units_ghost) > 0
    assert len(units_night) > 0

    # 3. Create Infrastructure correlate payload for shared Analytics ID & Certificate
    shared_cert_payload = {
        "left_entity_id": "actor_ghostvendor",
        "right_entity_id": "actor_nightshade99",
        "indicator_type": "onionscan_analytics_id",
        "evidence": "UA-98765432-1",
        "source": "onionscan",
        "rarity": 0.85
    }
    adapter = InfraEvidenceAdapter()
    infra_units = adapter.extract(shared_cert_payload)

    # 4. Save evidence to DB
    all_units = units_ghost + units_night + infra_units
    for u in all_units:
        evidence_repo.save(u)

    # 5. Evaluate pair using Fusion Engine
    fusion = ExplainableFusionEngine()
    candidate_link = fusion.evaluate_pair(
        left_entity_id="actor_ghostvendor",
        right_entity_id="actor_nightshade99",
        evidence_units=infra_units
    )

    # 6. Verify category caps (Infrastructure alone capped at max_contribution 0.65 => tier <= possible_association)
    assert candidate_link.tier in ["possible_association", "unresolved", "insufficient_evidence"]
    assert candidate_link.score <= 0.70  # Cannot reach likely_same_actor (0.70+) on infrastructure alone

    # 7. Save candidate link to DB
    saved_link = link_repo.save_candidate_link(candidate_link)
    saved_link_id = saved_link["link_id"] if isinstance(saved_link, dict) else saved_link.link_id
    assert saved_link_id == candidate_link.link_id
