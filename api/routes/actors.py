from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Request
from db.repositories.entity_repo import EntityRepository
from db.repositories.link_repo import LinkRepository
from db.repositories.evidence_repo import EvidenceRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/actors", tags=["Actor Profiles"])

DISCLOSURE = (
    "This system provides confidence-scored technical associations for authorized "
    "analyst review. It does not defeat Tor, establish a person's real-world identity, "
    "or replace legal/forensic investigation."
)


def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)


@router.get("/{actor_id}")
def get_actor_profile(
    actor_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """
    Actor profile summary: entity record, its candidate links (with tier, score,
    category breakdown and limitations), and evidence counts. Returns an explicit
    absence state rather than a bare 404/empty when the actor has no data (EC-39).
    """
    entity = EntityRepository(db_path).get_by_id(actor_id)

    link_repo = LinkRepository(db_path)
    links = [l for l in link_repo.list_all(limit=10000)
             if l.get("left_entity_id") == actor_id or l.get("right_entity_id") == actor_id]

    evidence = EvidenceRepository(db_path).list_by_entity(actor_id)

    if entity is None and not links and not evidence:
        return {"actor_id": actor_id, "found": False,
                "absence_reason": "no_data_for_actor", "disclosure": DISCLOSURE}

    link_summaries = [{
        "link_id": l.get("link_id"),
        "other_entity": l.get("right_entity_id") if l.get("left_entity_id") == actor_id else l.get("left_entity_id"),
        "tier": l.get("tier"),
        "score": l.get("score"),
        "state": l.get("state"),
        "score_status": l.get("score_status"),
        "category_breakdown": l.get("category_breakdown_json") or l.get("category_breakdown"),
        "limitations": l.get("limitations_json") or l.get("limitations"),
        "explanation": l.get("explanation"),
    } for l in links]

    return {
        "actor_id": actor_id,
        "found": True,
        "entity": entity,
        "links": link_summaries,
        "link_count": len(link_summaries),
        "evidence_count": len(evidence),
        "disclosure": DISCLOSURE,
    }
