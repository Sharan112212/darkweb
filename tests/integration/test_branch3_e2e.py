"""
Integration Test: Branch 3 End-to-End Pipeline.
Validates the complete analytical pipeline:
1. Raw signal extraction through Ingestion Adapters (Identity & Stylometry) -> Canonical EvidenceUnits
2. Persistence into canonical EvidenceRepository
3. Multi-Signal Explainable Fusion (Noisy-OR, Category classification, Caps, Tier mapping) -> CandidateLink
4. Competing Link Conflict Resolution (ConflictResolver, conflict_set_id)
5. Candidate Link Lifecycle Management (LinkLifecycleManager, state transitions, versioning)
6. Immutable Snapshot Audit Verification (candidate_link_versions)
7. End-to-end idempotency & calculation input hash stability
"""
import pytest
from adapters.identity_evidence_adapter import IdentityEvidenceAdapter
from adapters.minilm_evidence_adapter import MiniLMEvidenceAdapter
from db.repositories.evidence_repo import EvidenceRepository
from db.repositories.link_repo import LinkRepository
from fusion.explainable_fusion import ExplainableFusionEngine
from fusion.conflict_resolver import ConflictResolver
from fusion.link_lifecycle import LinkLifecycleManager
from models.enums import Tier, LinkState, ScoreStatus


def test_branch3_e2e_full_attribution_lifecycle(temp_db):
    """
    End-to-End test of the Branch 3 fusion pipeline:
    adapter -> evidence_repo -> explainable_fusion -> conflict_resolver -> link_lifecycle -> link_versions
    """
    evidence_repo = EvidenceRepository(temp_db)
    link_repo = LinkRepository(db_path_or_url=temp_db)
    identity_adapter = IdentityEvidenceAdapter()
    stylometry_adapter = MiniLMEvidenceAdapter()
    fusion_engine = ExplainableFusionEngine()
    lifecycle_mgr = LinkLifecycleManager(db_path=temp_db)

    # --------------------------------------------------------------------------
    # Step 1: Extract Canonical EvidenceUnits via Ingestion Adapters
    # --------------------------------------------------------------------------
    raw_identity_payload = {
        "actor_a": "ViperX",
        "actor_b": "ViperX_Reborn",
        "evidence": "Wallet Address: 3GhostVendorFakeWallet000000000000",
        "capture_id": "cap_viperx_001",
        "source_url": "http://market.onion/vendor/ViperX",
        "source": "market_alpha",
    }
    identity_units = identity_adapter.extract(raw_identity_payload)
    assert len(identity_units) == 1
    u_wallet = identity_units[0]
    assert u_wallet.category == "K"
    assert u_wallet.indicator_type == "wallet_address"
    assert u_wallet.confidence_weight == 0.90

    raw_stylometry_payload = {
        "actor_a": "ViperX",
        "actor_b": "ViperX_Reborn",
        "similarity": 0.85,
        "post_count_a": 10,
        "post_count_b": 10,
        "char_count_a": 2000,
        "char_count_b": 2000,
        "capture_id": "cap_viperx_002",
        "source": "forum_obsidian",
        "source_url": "http://obsidian.onion/thread/99",
    }
    stylometry_units = stylometry_adapter.extract(raw_stylometry_payload)
    assert len(stylometry_units) == 1
    u_stylometry = stylometry_units[0]
    assert u_stylometry.category == "S"
    assert u_stylometry.indicator_type == "semantic_similarity"
    assert u_stylometry.confidence_weight == 0.72

    # --------------------------------------------------------------------------
    # Step 2: Persist Canonical EvidenceUnits into Database
    # --------------------------------------------------------------------------
    evidence_repo.save(u_wallet)
    evidence_repo.save(u_stylometry)
    assert evidence_repo.count() == 2

    stored_evidence = evidence_repo.list_by_pair("ViperX", "ViperX_Reborn")
    assert len(stored_evidence) == 2

    # --------------------------------------------------------------------------
    # Step 3: Explainable Fusion Engine (Noisy-OR & Multi-Signal Boost)
    # --------------------------------------------------------------------------
    candidate_link = fusion_engine.evaluate_pair(
        left_entity_id="ViperX_Reborn",
        right_entity_id="ViperX",
        evidence_units=stored_evidence,
    )

    # Normalized entity ordering
    assert candidate_link.left_entity_id == "ViperX"
    assert candidate_link.right_entity_id == "ViperX_Reborn"

    # Multi-signal boost: K (0.90) + S (capped at 0.20) -> 1 - (0.10 * 0.80) = 0.9200
    assert candidate_link.score == pytest.approx(0.920, abs=0.001)
    assert candidate_link.tier == Tier.observed_technical_identity.value
    assert candidate_link.state == LinkState.proposed.value
    assert candidate_link.link_version == 1
    assert candidate_link.calculation_input_hash.startswith("sha256:")

    # Breakdown verification
    assert candidate_link.category_breakdown["K"]["score"] == 0.90
    assert candidate_link.category_breakdown["S"]["score"] == 0.20
    assert candidate_link.category_breakdown["I"]["state"] == "not_available"
    assert candidate_link.category_breakdown["B"]["state"] == "not_available"

    # Save candidate link
    link_repo.save_candidate_link(candidate_link.model_dump())

    # --------------------------------------------------------------------------
    # Step 4: Competing Hypotheses Conflict Resolution
    # --------------------------------------------------------------------------
    # Introduce competing candidate link: ViperX linked to ViperAlt via another signal
    competing_raw = {
        "actor_a": "ViperX",
        "actor_b": "ViperAlt",
        "evidence": "Wallet Address: 1ViperAltCompetitorWallet000000000",
        "capture_id": "cap_viperx_003",
        "source_url": "http://market.onion/vendor/ViperAlt",
    }
    comp_units = identity_adapter.extract(competing_raw)
    for u in comp_units:
        evidence_repo.save(u)

    competing_link = fusion_engine.evaluate_pair("ViperX", "ViperAlt", comp_units)
    link_repo.save_candidate_link(competing_link.model_dump())

    # Run conflict resolution across both active candidate links
    resolved_links = ConflictResolver.resolve_conflicts([candidate_link, competing_link])
    res_map = {l.link_id: l for l in resolved_links}

    r_main = res_map[candidate_link.link_id]
    r_comp = res_map[competing_link.link_id]

    assert r_main.conflict_set_id is not None
    assert r_main.conflict_set_id == r_comp.conflict_set_id
    assert r_main.competing_link_ids == [competing_link.link_id]
    assert r_comp.competing_link_ids == [candidate_link.link_id]

    # Persist conflict annotations
    link_repo.save_candidate_link(r_main.model_dump())
    link_repo.save_candidate_link(r_comp.model_dump())

    # --------------------------------------------------------------------------
    # Step 5: Candidate Link Lifecycle Management (State Transitions)
    # --------------------------------------------------------------------------
    # Transition 1: proposed -> needs_review (triage for competing hypotheses)
    link_rev = lifecycle_mgr.submit_for_review(
        r_main,
        changed_by="triage_bot",
        reason="Flagged for analyst review due to competing link hypothesis",
    )
    assert link_rev.state == LinkState.needs_review.value
    assert link_rev.link_version == 2

    # Transition 2: needs_review -> accepted (analyst resolves conflict)
    link_acc = lifecycle_mgr.accept(
        link_rev,
        changed_by="senior_analyst_smith",
        reason="ViperX_Reborn confirmed through stylometric match and temporal succession",
    )
    assert link_acc.state == LinkState.accepted.value
    assert link_acc.link_version == 3

    # Competing link is rejected
    link_rej = lifecycle_mgr.reject(
        r_comp,
        changed_by="senior_analyst_smith",
        reason="ViperAlt determined to be escrow deposit artifact",
    )
    assert link_rej.state == LinkState.rejected.value

    # --------------------------------------------------------------------------
    # Step 6: Immutable Snapshot Audit History Verification
    # --------------------------------------------------------------------------
    versions = lifecycle_mgr.get_history(candidate_link.link_id)
    assert len(versions) == 3

    v1, v2, v3 = versions[0], versions[1], versions[2]
    assert v1["link_version"] == 1
    assert v1["state"] == "proposed"

    assert v2["link_version"] == 2
    assert v2["state"] == "needs_review"
    assert v2["changed_by"] == "triage_bot"
    assert "competing link" in v2["reason"].lower()

    assert v3["link_version"] == 3
    assert v3["state"] == "accepted"
    assert v3["changed_by"] == "senior_analyst_smith"
    assert "confirmed" in v3["reason"].lower()

    # --------------------------------------------------------------------------
    # Step 7: Idempotency & Calculation Input Hash Verification
    # --------------------------------------------------------------------------
    re_evaluated = fusion_engine.evaluate_pair(
        left_entity_id="ViperX",
        right_entity_id="ViperX_Reborn",
        evidence_units=stored_evidence,
    )
    assert re_evaluated.calculation_input_hash == candidate_link.calculation_input_hash
    assert re_evaluated.score == candidate_link.score
    assert re_evaluated.tier == candidate_link.tier
