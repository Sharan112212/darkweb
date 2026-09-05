from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Request
from db.repositories.timeline_repo import TimelineRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/actors", tags=["Timeline"])


def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)


@router.get("/{actor_id}/timeline")
def get_actor_timeline(
    actor_id: str,
    request: Request,
    from_date: Optional[str] = Query(None, alias="from", description="ISO-8601 UTC lower bound (inclusive)"),
    to_date: Optional[str] = Query(None, alias="to", description="ISO-8601 UTC upper bound (inclusive)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """
    Date-bounded timeline for an actor/entity. The same `from`/`to` filter is
    applied here and by the graph view so the two stay consistent. Returns an
    explicit absence reason rather than a bare empty list (EC-39), and flags
    `truncated` when more events exist than the page returned.
    """
    repo = TimelineRepository(db_path)
    events: List[Dict[str, Any]] = repo.list_by_entity(actor_id, limit=10000)

    # Date filtering on ISO-8601 timestamps (lexicographic compare is valid for UTC ISO).
    def _in_range(ev: Dict[str, Any]) -> bool:
        ts = str(ev.get("timestamp", ""))
        if from_date and ts < from_date:
            return False
        if to_date and ts > to_date:
            return False
        return True

    filtered = [e for e in events if _in_range(e)]
    total = len(filtered)
    page = filtered[offset: offset + limit]
    truncated = (offset + limit) < total

    if total == 0:
        reason = "no_timeline_events" if not events else "no_events_in_selected_range"
        return {
            "actor_id": actor_id,
            "events": [],
            "total": 0,
            "returned": 0,
            "truncated": False,
            "absence_reason": reason,
            "timezone": "UTC",
            "filters": {"from": from_date, "to": to_date},
        }

    return {
        "actor_id": actor_id,
        "events": page,
        "total": total,
        "returned": len(page),
        "truncated": truncated,
        "timezone": "UTC",
        "filters": {"from": from_date, "to": to_date, "limit": limit, "offset": offset},
    }
