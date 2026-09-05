from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional, List, Dict, Any
from governance.audit import AuditStore
from api.rbac import ROLE_HIERARCHY

router = APIRouter(prefix="/v1/audit", tags=["Audit Log"])

# Global audit store singleton for API layer
global_audit_store = AuditStore()

def verify_role(user_role: str, min_role: str):
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    min_level = ROLE_HIERARCHY.get(min_role, 99)
    if user_level < min_level:
        raise HTTPException(status_code=403, detail=f"Forbidden: Role '{user_role}' lacks required permissions (minimum: '{min_role}').")

@router.get("", response_model=Dict[str, Any])
def query_audit_log(
    x_user_role: str = Header("admin", alias="X-User-Role"),
    user_id: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None)
):
    verify_role(x_user_role, min_role="admin")
    events = global_audit_store.list_events(user_id=user_id, object_id=object_id)
    is_valid, msg = global_audit_store.verify_integrity()

    return {
        "integrity_verified": is_valid,
        "integrity_message": msg,
        "total_records": len(events),
        "events": [e.model_dump() for e in events]
    }
