"""
Unit tests for LinkLifecycleManager and CandidateLink state machine / versioning.
Tests:
- Valid state transitions (proposed -> needs_review -> accepted -> rejected -> superseded).
- Terminal state enforcement (superseded cannot transition).
- Reversibility of analyst decisions (accepted <-> rejected <-> needs_review).
- Automatic link_version incrementing.
- Immutable version snapshot creation in candidate_link_versions table with changed_by and reason.
- Lifecycle convenience methods (submit_for_review, accept, reject, supersede).
- Link ID string lookup support during transition.
"""
import pytest
from fusion.link_lifecycle import LinkLifecycleManager
from models.candidate_link import CandidateLink
from models.enums import LinkState, Tier, ScoreStatus


def _create_initial_link(temp_db, link_id: str = "lnk_life_001") -> CandidateLink:
    """Helper to save an initial CandidateLink into the database."""
    mgr = LinkLifecycleManager(db_path=temp_db)
    link = CandidateLink(
        link_id=link_id,
        link_version=1,
        left_entity_id="DarkFox",
        right_entity_id="DarkFox_v2",
        state=LinkState.proposed.value,
        score=0.95,
        tier=Tier.observed_technical_identity.value,
        score_status=ScoreStatus.observed.value,
        category_breakdown={"K": {"score": 0.95, "state": "observed", "evidence_ids": ["ev_1"]}},
        evidence_ids=["ev_1"],
        explanation="Initial proposed candidate link based on PGP match.",
        limitations=["Subject to analyst confirmation."],
        score_model_version="scoring-v1.0",
        calculation_input_hash="sha256:testinitcalchash123",
        created_at="2026-09-05T10:00:00Z",
        updated_at="2026-09-05T10:00:00Z",
    )
    # Save initial version
    mgr.link_repo.save_candidate_link(link.model_dump())
    return link


# ==============================================================================
# 1. State Transitions & Version Bumping
# ==============================================================================

def test_proposed_to_needs_review(temp_db):
    """Transition from proposed to needs_review bumps version to 2."""
    mgr = LinkLifecycleManager(db_path=temp_db)
    link = _create_initial_link(temp_db)

    updated = mgr.transition_state(
        link,
        LinkState.needs_review.value,
        changed_by="lead_analyst",
        reason="Assigned for verification",
    )

    assert updated.state == LinkState.needs_review.value
    assert updated.link_version == 2


def test_needs_review_to_accepted(temp_db):
    """Transition from needs_review to accepted."""
    mgr = LinkLifecycleManager(db_path=temp_db)
    link = _create_initial_link(temp_db)

    link_rev = mgr.submit_for_review(link, changed_by="system", reason="Queue triage")
    assert link_rev.state == LinkState.needs_review.value
    assert link_rev.link_version == 2

    link_acc = mgr.accept(link_rev, changed_by="analyst_42", reason="PGP signature validated")
    assert link_acc.state == LinkState.accepted.value
    assert link_acc.link_version == 3


def test_reversible_analyst_decisions(temp_db):
    """Analyst decisions are reversible: accepted -> rejected -> accepted."""
    mgr = LinkLifecycleManager(db_path=temp_db)
    link = _create_initial_link(temp_db)

    # proposed -> accepted
    link_acc = mgr.accept(link, changed_by="analyst_1", reason="Initial confirmation")
    assert link_acc.state == LinkState.accepted.value

    # accepted -> rejected (false positive discovered)
    link_rej = mgr.reject(link_acc, changed_by="supervisor", reason="Key found on public escrow")
    assert link_rej.state == LinkState.rejected.value
    assert link_rej.link_version == 3

    # rejected -> needs_review (reopened with new evidence)
    link_rev = mgr.submit_for_review(link_rej, changed_by="analyst_2", reason="Re-evaluating")
    assert link_rev.state == LinkState.needs_review.value
    assert link_rev.link_version == 4


def test_terminal_superseded_state(temp_db):
    """
    Once in superseded state, attempting any further transition must raise ValueError.
    """
    mgr = LinkLifecycleManager(db_path=temp_db)
    link = _create_initial_link(temp_db)

    link_sup = mgr.supersede(link, changed_by="system", reason="Superseded by batch run 12")
    assert link_sup.state == LinkState.superseded.value

    with pytest.raises(ValueError, match="Invalid state transition"):
        mgr.transition_state(link_sup, LinkState.accepted.value)

    with pytest.raises(ValueError, match="Invalid state transition"):
        mgr.transition_state(link_sup, LinkState.needs_review.value)


def test_invalid_state_name_raises_value_error(temp_db):
    """Passing a non-existent state name raises ValueError."""
    mgr = LinkLifecycleManager(db_path=temp_db)
    link = _create_initial_link(temp_db)

    with pytest.raises(ValueError, match="Unknown state"):
        mgr.transition_state(link, "unknown_custom_state")


# ==============================================================================
# 2. Immutable Version Snapshots & History
# ==============================================================================

def test_immutable_history_records_in_db(temp_db):
    """
    Each state transition must persist an immutable row in candidate_link_versions
    with the exact changed_by and reason values.
    """
    mgr = LinkLifecycleManager(db_path=temp_db)
    link = _create_initial_link(temp_db, link_id="lnk_audit_test")

    mgr.submit_for_review(link, changed_by="analyst_bob", reason="Submitted for peer review")
    mgr.accept(link, changed_by="chief_carter", reason="Attribution approved for report")

    # Fetch version history from DB
    history = mgr.get_history("lnk_audit_test")
    assert len(history) == 3  # Initial (v1) + review (v2) + accept (v3)

    versions = [h["link_version"] for h in history]
    states = [h["state"] for h in history]
    changers = [h["changed_by"] for h in history]
    reasons = [h["reason"] for h in history]

    assert versions == [1, 2, 3]
    assert states == ["proposed", "needs_review", "accepted"]
    assert changers[1] == "analyst_bob"
    assert reasons[1] == "Submitted for peer review"
    assert changers[2] == "chief_carter"
    assert reasons[2] == "Attribution approved for report"


# ==============================================================================
# 3. Transition via Link ID String Lookup
# ==============================================================================

def test_transition_by_link_id_string(temp_db):
    """LinkLifecycleManager.transition_state must support string link_id argument."""
    mgr = LinkLifecycleManager(db_path=temp_db)
    link = _create_initial_link(temp_db, link_id="lnk_string_lookup")

    updated = mgr.transition_state(
        "lnk_string_lookup",
        LinkState.needs_review.value,
        changed_by="service_api",
        reason="Transition via REST link_id",
    )

    assert isinstance(updated, CandidateLink)
    assert updated.link_id == "lnk_string_lookup"
    assert updated.state == LinkState.needs_review.value
    assert updated.link_version == 2


def test_transition_non_existent_link_id_raises_value_error(temp_db):
    """Attempting to transition a non-existent link_id string raises ValueError."""
    mgr = LinkLifecycleManager(db_path=temp_db)

    with pytest.raises(ValueError, match="not found in database"):
        mgr.transition_state("lnk_does_not_exist", LinkState.needs_review.value)
