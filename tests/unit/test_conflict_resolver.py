"""
Unit tests for ConflictResolver (competing hypothesis detection and conflict sets per EC-13).
Tests:
- Detection of competing links sharing an entity (e.g. Actor A linked to both B and C).
- Assignment of deterministic conflict_set_id derived from sorted member link IDs.
- Correct population of competing_link_ids array for all participants.
- Isolation of non-competing / disjoint links (conflict_set_id remains None).
- Transitive / connected component multi-way conflict clustering.
- Order invariance of conflict_set_id generation.
- Dict and CandidateLink object interoperability.
- identify_conflicts grouped mapping method.
"""
import pytest
from fusion.conflict_resolver import ConflictResolver
from models.candidate_link import CandidateLink
from models.enums import Tier, LinkState, ScoreStatus


def _create_link(link_id: str, left: str, right: str, score: float = 0.85) -> CandidateLink:
    return CandidateLink(
        link_id=link_id,
        link_version=1,
        left_entity_id=min(left, right),
        right_entity_id=max(left, right),
        state=LinkState.proposed.value,
        score=score,
        tier=Tier.likely_same_actor.value,
        score_status=ScoreStatus.observed.value,
        category_breakdown={},
        evidence_ids=["ev_dummy"],
        explanation="Test link for conflict resolution.",
        calculation_input_hash=f"sha256:hash_{link_id}",
        created_at="2026-09-05T12:00:00Z",
        updated_at="2026-09-05T12:00:00Z",
    )


# ==============================================================================
# 1. Basic & Edge Cases
# ==============================================================================

def test_resolve_conflicts_empty_list():
    """Empty list must return empty list."""
    assert ConflictResolver.resolve_conflicts([]) == []


def test_resolve_conflicts_single_link_has_no_conflict():
    """Single link has no competitors: conflict_set_id must be None."""
    link = _create_link("lnk_1", "ActorA", "ActorB")
    resolved = ConflictResolver.resolve_conflicts([link])

    assert len(resolved) == 1
    assert resolved[0].conflict_set_id is None
    assert resolved[0].competing_link_ids == []


def test_resolve_conflicts_disjoint_links_have_no_conflict():
    """Two completely independent entity pairs have no conflict."""
    link1 = _create_link("lnk_1", "ActorA", "ActorB")
    link2 = _create_link("lnk_2", "ActorC", "ActorD")

    resolved = ConflictResolver.resolve_conflicts([link1, link2])

    for l in resolved:
        assert l.conflict_set_id is None
        assert l.competing_link_ids == []


# ==============================================================================
# 2. Competing Hypotheses Detection
# ==============================================================================

def test_competing_pair_detection_and_conflict_set_id():
    """
    ActorA is linked to ActorB (Link 1) AND ActorA is linked to ActorC (Link 2).
    Both links must be flagged as competing, share the identical conflict_set_id,
    and reference each other in competing_link_ids.
    """
    link1 = _create_link("lnk_001", "ActorA", "ActorB")
    link2 = _create_link("lnk_002", "ActorA", "ActorC")

    resolved = ConflictResolver.resolve_conflicts([link1, link2])
    res_map = {l.link_id: l for l in resolved}

    r1 = res_map["lnk_001"]
    r2 = res_map["lnk_002"]

    # Both must have non-null conflict_set_id
    assert r1.conflict_set_id is not None
    assert r1.conflict_set_id.startswith("conf_")

    # Both links must share the exact same conflict_set_id
    assert r1.conflict_set_id == r2.conflict_set_id

    # Cross-referenced competing IDs
    assert r1.competing_link_ids == ["lnk_002"]
    assert r2.competing_link_ids == ["lnk_001"]


def test_disjoint_link_remains_unaffected_by_competing_cluster():
    """
    Cluster (ActorA-ActorB, ActorA-ActorC) is competing,
    while Link 3 (ActorX-ActorY) is completely disjoint.
    Link 3 must have conflict_set_id = None.
    """
    link1 = _create_link("lnk_001", "ActorA", "ActorB")
    link2 = _create_link("lnk_002", "ActorA", "ActorC")
    link3 = _create_link("lnk_003", "ActorX", "ActorY")

    resolved = ConflictResolver.resolve_conflicts([link1, link2, link3])
    res_map = {l.link_id: l for l in resolved}

    assert res_map["lnk_001"].conflict_set_id == res_map["lnk_002"].conflict_set_id
    assert res_map["lnk_003"].conflict_set_id is None
    assert res_map["lnk_003"].competing_link_ids == []


# ==============================================================================
# 3. Three-Way / Transitive Conflict Clustering
# ==============================================================================

def test_transitive_conflict_clustering():
    """
    Link 1: ActorA <-> ActorB
    Link 2: ActorB <-> ActorC
    Link 3: ActorC <-> ActorD
    All 3 links form a connected component through shared endpoints
    and must share the same conflict_set_id.
    """
    link1 = _create_link("lnk_1", "ActorA", "ActorB")
    link2 = _create_link("lnk_2", "ActorB", "ActorC")
    link3 = _create_link("lnk_3", "ActorC", "ActorD")

    resolved = ConflictResolver.resolve_conflicts([link1, link2, link3])
    csids = {l.conflict_set_id for l in resolved}

    assert len(csids) == 1
    common_csid = csids.pop()
    assert common_csid.startswith("conf_")

    for l in resolved:
        assert l.conflict_set_id == common_csid
        # Competing link IDs must contain all other members in the conflict set
        assert set(l.competing_link_ids) == {other.link_id for other in resolved if other.link_id != l.link_id}


# ==============================================================================
# 4. Determinism & Order Invariance
# ==============================================================================

def test_conflict_set_id_order_invariance():
    """Resolving the same links in different order yields identical conflict_set_id."""
    l1 = _create_link("lnk_alpha", "ActorA", "ActorB")
    l2 = _create_link("lnk_beta", "ActorA", "ActorC")
    l3 = _create_link("lnk_gamma", "ActorA", "ActorD")

    res_forward = ConflictResolver.resolve_conflicts([l1, l2, l3])
    res_reverse = ConflictResolver.resolve_conflicts([l3, l2, l1])

    csid_forward = res_forward[0].conflict_set_id
    csid_reverse = res_reverse[0].conflict_set_id

    assert csid_forward == csid_reverse


# ==============================================================================
# 5. Dict Input Interoperability & identify_conflicts Helper
# ==============================================================================

def test_conflict_resolver_supports_dictionaries():
    """ConflictResolver must seamlessly support raw dictionary inputs."""
    d1 = {"link_id": "lnk_1", "left_entity_id": "A", "right_entity_id": "B"}
    d2 = {"link_id": "lnk_2", "left_entity_id": "A", "right_entity_id": "C"}

    resolved = ConflictResolver.resolve_conflicts([d1, d2])

    assert d1["conflict_set_id"] is not None
    assert d1["conflict_set_id"] == d2["conflict_set_id"]
    assert d1["competing_link_ids"] == ["lnk_2"]
    assert d2["competing_link_ids"] == ["lnk_1"]


def test_identify_conflicts_mapping():
    """identify_conflicts helper must return a dict mapping conflict_set_id to member links."""
    link1 = _create_link("lnk_001", "ActorA", "ActorB")
    link2 = _create_link("lnk_002", "ActorA", "ActorC")
    link3 = _create_link("lnk_003", "ActorIsolated1", "ActorIsolated2")

    conflict_map = ConflictResolver.identify_conflicts([link1, link2, link3])

    assert len(conflict_map) == 1
    csid, members = next(iter(conflict_map.items()))
    assert csid.startswith("conf_")
    assert len(members) == 2
    member_ids = {m.link_id for m in members}
    assert member_ids == {"lnk_001", "lnk_002"}
