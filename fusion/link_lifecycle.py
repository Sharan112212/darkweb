"""
LinkLifecycleManager Module.
Manages the candidate link state machine and historical versioning:
proposed -> needs_review -> accepted | rejected | superseded
Saves new version snapshots to LinkRepository with changed_by, reason, and incremented link_version.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union

from db.repositories.link_repo import LinkRepository
from models.candidate_link import CandidateLink
from models.enums import LinkState


class LinkLifecycleManager:
    """
    Manages state machine transitions and audit snapshots for CandidateLink instances:
      - proposed -> needs_review -> accepted | rejected | superseded
      - Enforces strict transition validity
      - Reversible decisions for analysts (accepted <-> rejected <-> needs_review)
      - Terminal superseded state
      - Saves new version records with changed_by and reason via LinkRepository
    """

    VALID_TRANSITIONS: Dict[str, Set[str]] = {
        LinkState.proposed.value: {
            LinkState.needs_review.value,
            LinkState.accepted.value,
            LinkState.rejected.value,
            LinkState.superseded.value,
        },
        LinkState.needs_review.value: {
            LinkState.accepted.value,
            LinkState.rejected.value,
            LinkState.superseded.value,
        },
        LinkState.accepted.value: {
            LinkState.needs_review.value,
            LinkState.rejected.value,
            LinkState.superseded.value,
        },
        LinkState.rejected.value: {
            LinkState.needs_review.value,
            LinkState.accepted.value,
            LinkState.superseded.value,
        },
        LinkState.superseded.value: set(),  # Terminal state
    }

    def __init__(
        self,
        link_repository: Optional[LinkRepository] = None,
        db_path: Optional[str] = None,
    ):
        if link_repository is not None:
            self.link_repo = link_repository
        else:
            self.link_repo = LinkRepository(db_path_or_url=db_path)

    def transition_state(
        self,
        link: Union[CandidateLink, Dict[str, Any], str],
        new_state: Union[str, LinkState],
        changed_by: str = "analyst",
        reason: str = "Lifecycle state transition",
    ) -> CandidateLink:
        """
        Transitions a candidate link to a new lifecycle state.
        Bumps link_version, updates timestamps, and persists an immutable version record.

        Args:
            link: CandidateLink instance, dict, or link_id string.
            new_state: Target state ('proposed', 'needs_review', 'accepted', 'rejected', 'superseded').
            changed_by: Identifier of the analyst or automated system making the change.
            reason: Mandatory explanation / rationale for the transition.

        Returns:
            Updated CandidateLink instance.
        """
        target_state = new_state.value if isinstance(new_state, LinkState) else str(new_state).strip()

        all_states = {s.value for s in LinkState}
        if target_state not in all_states:
            raise ValueError(f"Unknown state '{target_state}'. Valid states are: {sorted(list(all_states))}")

        # Resolve link data
        if isinstance(link, str):
            row = self.link_repo.get_by_id(link)
            if not row:
                raise ValueError(f"CandidateLink with id '{link}' not found in database.")
            link_data = dict(row)
        elif isinstance(link, CandidateLink):
            link_data = link.model_dump()
        elif isinstance(link, dict):
            link_data = dict(link)
        else:
            raise TypeError(f"Unsupported link type: {type(link)}")

        current_state = link_data.get("state", LinkState.proposed.value)
        allowed = self.VALID_TRANSITIONS.get(current_state, set())

        if target_state != current_state and target_state not in allowed:
            raise ValueError(
                f"Invalid state transition from '{current_state}' to '{target_state}'. "
                f"Allowed transitions from '{current_state}': {sorted(list(allowed))}"
            )

        # Increment version and update timestamps
        current_version = int(link_data.get("link_version", 1))
        next_version = current_version + 1

        link_data["state"] = target_state
        link_data["link_version"] = next_version
        link_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        link_data["changed_by"] = changed_by
        link_data["reason"] = reason

        # Persist to repository (creates immutable version record)
        saved = self.link_repo.save_candidate_link(link_data)

        # Deserialize fields if returned with _json suffix
        breakdown = saved.get("category_breakdown")
        if breakdown is None:
            breakdown = saved.get("category_breakdown_json", {})

        ev_ids = saved.get("evidence_ids")
        if ev_ids is None:
            ev_ids = saved.get("evidence_ids_json", [])

        competing_ids = saved.get("competing_link_ids")
        if competing_ids is None:
            competing_ids = saved.get("competing_link_ids_json", [])

        limits = saved.get("limitations")
        if limits is None:
            limits = saved.get("limitations_json", [])

        return CandidateLink(
            link_id=saved["link_id"],
            link_version=int(saved["link_version"]),
            left_entity_id=saved["left_entity_id"],
            right_entity_id=saved["right_entity_id"],
            state=saved["state"],
            score=float(saved["score"]),
            tier=saved["tier"],
            score_status=saved.get("score_status", "observed"),
            category_breakdown=breakdown,
            evidence_ids=ev_ids,
            conflict_set_id=saved.get("conflict_set_id"),
            competing_link_ids=competing_ids,
            explanation=saved.get("explanation", ""),
            limitations=limits,
            score_model_version=saved.get("score_model_version", "scoring-v1.0"),
            calculation_input_hash=saved.get("calculation_input_hash", ""),
            created_at=saved.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=saved.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )

    def submit_for_review(
        self,
        link: Union[CandidateLink, Dict[str, Any], str],
        changed_by: str = "system",
        reason: str = "Candidate link submitted for analyst review",
    ) -> CandidateLink:
        """Transitions candidate link to 'needs_review'."""
        return self.transition_state(link, LinkState.needs_review.value, changed_by=changed_by, reason=reason)

    def accept(
        self,
        link: Union[CandidateLink, Dict[str, Any], str],
        changed_by: str = "analyst",
        reason: str = "Candidate link accepted by analyst",
    ) -> CandidateLink:
        """Transitions candidate link to 'accepted'."""
        return self.transition_state(link, LinkState.accepted.value, changed_by=changed_by, reason=reason)

    def reject(
        self,
        link: Union[CandidateLink, Dict[str, Any], str],
        changed_by: str = "analyst",
        reason: str = "Candidate link rejected by analyst",
    ) -> CandidateLink:
        """Transitions candidate link to 'rejected'."""
        return self.transition_state(link, LinkState.rejected.value, changed_by=changed_by, reason=reason)

    def supersede(
        self,
        link: Union[CandidateLink, Dict[str, Any], str],
        changed_by: str = "system",
        reason: str = "Candidate link superseded by newer evidence/version",
    ) -> CandidateLink:
        """Transitions candidate link to 'superseded'."""
        return self.transition_state(link, LinkState.superseded.value, changed_by=changed_by, reason=reason)

    def get_history(self, link_id: str) -> List[Dict[str, Any]]:
        """Retrieves immutable historical version snapshots for a candidate link."""
        return self.link_repo.get_versions(link_id)
