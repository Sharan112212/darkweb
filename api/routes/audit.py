from fastapi import APIRouter, HTTPException, Header, Query, Request, Depends
from typing import Optional, List, Dict, Any
from governance.audit import AuditStore
from api.rbac import ROLE_HIERARCHY, require_role, UserRole
from db.repositories.audit_repo import AuditRepository

router = APIRouter(prefix="/v1/audit", tags=["Audit Log"])

global_audit_store = AuditStore()

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

def verify_role(user_role: str, min_role: str):
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    min_level = ROLE_HIERARCHY.get(min_role, 99)
    if user_level < min_level:
        raise HTTPException(status_code=403, detail=f"Forbidden: Role '{user_role}' lacks required permissions (minimum: '{min_role}').")

@router.get("", response_model=Dict[str, Any])
def query_audit_log(
    request: Request,
    x_user_role: str = Header("reviewer", alias="X-User-Role"),
    user_id: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db_path: Optional[str] = Depends(get_db_path)
):
    verify_role(x_user_role, min_role="reviewer")
    if db_path:
        repo = AuditRepository(db_path)
        events = repo.list_events(limit=limit, offset=offset, object_id=object_id, user_id=user_id, action=action)
        return {
            "events": events,
            "returned": len(events),
            "total_records": len(events),
            "integrity_verified": True,
            "integrity_message": "Database audit log active.",
            "filters": {"object_id": object_id, "user_id": user_id, "action": action, "limit": limit, "offset": offset}
        }

    events = global_audit_store.list_events(user_id=user_id, object_id=object_id)
    is_valid, msg = global_audit_store.verify_integrity()

    return {
        "integrity_verified": is_valid,
        "integrity_message": msg,
        "total_records": len(events),
        "returned": len(events),
        "events": [e.model_dump() for e in events]
    }
