"""
Timeline Event Builder (Branch 6).

Generates TimelineEvent records from evidence, candidate links, and analyst
decisions. Uses the three time fields consistently and never invents dates:

  1. source_claimed_time  — what the source claims (may be forged; EC-16)
  2. observation_date     — when the indicator was observed
  3. captured_at          — when WE captured it (always present, UTC; EC-17)

The chosen timestamp is recorded in metadata ("time_basis") together with a
numeric time_confidence and a human label, so uncertain dates are marked rather
than presented as definitive.
"""
import hashlib
from typing import List, Dict, Any, Optional, Iterable

from models.audit import TimelineEvent
from models.evidence import EvidenceUnit
from models.candidate_link import CandidateLink

# indicator_type -> timeline event_type
_INDICATOR_EVENT_TYPE = {
    "pgp_fingerprint": "pgp_seen",
    "wallet_address": "wallet_seen",
    "contact_identifier": "contact_seen",
    "alias": "alias_observed",
    "certificate_fingerprint": "infrastructure_observation",
    "infrastructure_match": "infrastructure_observation",
    "semantic_similarity": "post_observed",
    "classical_stylometry": "post_observed",
    "posting_time_pattern": "post_observed",
    "vocabulary_overlap": "post_observed",
    "template_match": "post_observed",
    "persona_migration_candidate": "post_observed",
}


def _event_type_for(indicator_type: str) -> str:
    if indicator_type.startswith("onionscan_"):
        return "infrastructure_observation"
    return _INDICATOR_EVENT_TYPE.get(indicator_type, "observation")


def confidence_label(score: float) -> str:
    """Human label for a numeric time confidence."""
    if score >= 0.99:
        return "exact"
    if score >= 0.5:
        return "approximate"
    return "uncertain"


class TimelineEventBuilder:
    """Builds (and optionally persists) TimelineEvent records."""

    def _select_time(self, ev: EvidenceUnit):
        """
        Choose the event timestamp without inventing one.

        Returns (timestamp, confidence, basis). Prefers the source-claimed time
        (marked with the evidence's own time_confidence, since it may be forged),
        then the observation date, and finally the capture time (our own UTC clock
        — exact as a capture, but flagged as capture-time not event-time).
        """
        if ev.source_claimed_time:
            return ev.source_claimed_time, float(ev.time_confidence), "source_claimed_time"
        if ev.observation_date:
            return ev.observation_date, float(ev.time_confidence), "observation_date"
        # captured_at is always present and is our own clock.
        conf = 1.0 if ev.time_confidence >= 0.99 else float(ev.time_confidence)
        return ev.captured_at, conf, "captured_at"

    def build_from_evidence(
        self,
        evidence_units: Iterable[EvidenceUnit],
        entity_id: Optional[str] = None,
    ) -> List[TimelineEvent]:
        """
        Build one TimelineEvent per evidence unit, plus first_seen/last_seen
        bookends per entity. If entity_id is given, only that entity's evidence
        is included; otherwise events are emitted for every linked entity.
        """
        events: List[TimelineEvent] = []
        # (entity_id -> list of (timestamp, confidence)) for bookend computation
        per_entity_times: Dict[str, List[str]] = {}

        for ev in evidence_units:
            ts, conf, basis = self._select_time(ev)
            targets = [entity_id] if entity_id else list(ev.linked_entities)
            for ent in targets:
                if entity_id and ent != entity_id:
                    continue
                if ent not in ev.linked_entities:
                    continue
                events.append(self._make_event(
                    event_type=_event_type_for(ev.indicator_type),
                    entity_id=ent,
                    timestamp=ts,
                    time_confidence=conf,
                    time_basis=basis,
                    description=f"{ev.indicator_type} observed ({ev.source}): {ev.explanation}",
                    evidence_ids=[ev.evidence_id],
                    extra={"indicator_type": ev.indicator_type, "source": ev.source},
                ))
                per_entity_times.setdefault(ent, []).append(ts)

        # first_seen / last_seen bookends
        for ent, times in per_entity_times.items():
            ordered = sorted(times)
            events.append(self._make_event(
                event_type="first_seen", entity_id=ent, timestamp=ordered[0],
                time_confidence=0.9, time_basis="derived",
                description=f"First observation of {ent} across collected evidence.",
                evidence_ids=[], extra={"derived": True},
            ))
            events.append(self._make_event(
                event_type="last_seen", entity_id=ent, timestamp=ordered[-1],
                time_confidence=0.9, time_basis="derived",
                description=f"Most recent observation of {ent} across collected evidence.",
                evidence_ids=[], extra={"derived": True},
            ))

        return self._sort(events)

    def build_from_link(self, link: CandidateLink) -> List[TimelineEvent]:
        """candidate_link_created + score_change + analyst_decision events."""
        events: List[TimelineEvent] = []
        for ent in (link.left_entity_id, link.right_entity_id):
            events.append(self._make_event(
                event_type="candidate_link_created", entity_id=ent,
                timestamp=link.created_at, time_confidence=1.0, time_basis="captured_at",
                description=f"Candidate link {link.link_id} proposed (tier={link.tier}, score={link.score}).",
                evidence_ids=list(link.evidence_ids),
                extra={"link_id": link.link_id, "tier": link.tier, "score": link.score},
            ))
            if link.link_version > 1:
                events.append(self._make_event(
                    event_type="score_change", entity_id=ent,
                    timestamp=link.updated_at, time_confidence=1.0, time_basis="captured_at",
                    description=f"Link {link.link_id} updated to version {link.link_version} "
                                f"(tier={link.tier}, score={link.score}).",
                    evidence_ids=list(link.evidence_ids),
                    extra={"link_id": link.link_id, "link_version": link.link_version},
                ))
            if link.state in ("accepted", "rejected", "superseded"):
                events.append(self._make_event(
                    event_type="analyst_decision", entity_id=ent,
                    timestamp=link.updated_at, time_confidence=1.0, time_basis="captured_at",
                    description=f"Analyst decision on link {link.link_id}: {link.state}.",
                    evidence_ids=list(link.evidence_ids),
                    extra={"link_id": link.link_id, "state": link.state},
                ))
        return self._sort(events)

    def persist(self, events: Iterable[TimelineEvent], repo) -> int:
        """Persist events via a TimelineRepository. Returns the count written."""
        count = 0
        for ev in events:
            repo.append({
                "event_id": ev.event_id,
                "event_type": ev.event_type,
                "entity_id": ev.entity_id,
                "timestamp": ev.timestamp,
                # DB column is a label (VARCHAR); numeric score kept in metadata.
                "time_confidence": confidence_label(ev.time_confidence),
                "description": ev.description,
                "evidence_ids": ev.evidence_ids,
                "metadata": ev.metadata,
            })
            count += 1
        return count

    # ------------------------------------------------------------------ helpers

    def _make_event(
        self,
        event_type: str,
        entity_id: str,
        timestamp: str,
        time_confidence: float,
        time_basis: str,
        description: str,
        evidence_ids: List[str],
        extra: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        meta: Dict[str, Any] = {
            "time_basis": time_basis,
            "time_confidence_score": round(float(time_confidence), 4),
            "time_confidence_label": confidence_label(time_confidence),
            "approximate": time_confidence < 0.99,
        }
        if extra:
            meta.update(extra)
        digest = hashlib.sha256(
            f"{event_type}|{entity_id}|{timestamp}|{','.join(evidence_ids)}".encode()
        ).hexdigest()[:12]
        return TimelineEvent(
            event_id=f"tl_{digest}",
            event_type=event_type,
            entity_id=entity_id,
            timestamp=str(timestamp),
            time_confidence=round(float(time_confidence), 4),
            description=description,
            evidence_ids=list(evidence_ids),
            metadata=meta,
        )

    @staticmethod
    def _sort(events: List[TimelineEvent]) -> List[TimelineEvent]:
        # Chronological, then a stable event_id tiebreak so ordering is deterministic
        return sorted(events, key=lambda e: (str(e.timestamp), e.event_id))
