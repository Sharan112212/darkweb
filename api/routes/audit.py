from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Request
from db.repositories.audit_repo import AuditRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)


@router.get("")
def list_audit_events(
    request: Request,
    object_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    # Audit trail is reviewer/admin only (viewers/analysts cannot inspect it).
    user: dict = Depends(require_role([UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """Query the append-only audit log (reviewer/admin only)."""
    repo = AuditRepository(db_path)
    events = repo.list_events(limit=limit, offset=offset, object_id=object_id,
                              user_id=user_id, action=action)
    return {
        "events": events,
        "returned": len(events),
        "filters": {"object_id": object_id, "user_id": user_id, "action": action,
                    "limit": limit, "offset": offset},
    }
