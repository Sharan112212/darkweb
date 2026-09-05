import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from db.repositories.audit_repo import AuditRepository
from api.rbac import require_role, UserRole

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

router = APIRouter(prefix="/admin", tags=["Administration"])

SOURCES_YAML = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "config", "sources.yaml")


def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = ""


def _load_sources() -> List[Dict[str, Any]]:
    if yaml is None or not os.path.isfile(SOURCES_YAML):
        return []
    with open(SOURCES_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", [])


@router.get("/sources")
def list_sources(
    request: Request,
    user: dict = Depends(require_role([UserRole.admin.value])),
) -> Dict[str, Any]:
    """List configured collection sources (admin only)."""
    overrides = getattr(request.app.state, "source_overrides", {}) or {}
    sources = _load_sources()
    for s in sources:
        if s.get("id") in overrides:
            s = {**s, **overrides[s["id"]]}
    return {"sources": sources, "count": len(sources)}


@router.post("/kill-switch")
def set_kill_switch(
    body: KillSwitchRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """Toggle the global collection kill-switch (admin only). Audited."""
    request.app.state.kill_switch = body.enabled
    AuditRepository(db_path).append({
        "user_id": user.get("sub", "admin"),
        "action": "kill_switch_toggle",
        "object_id": "global",
        "details": {"enabled": body.enabled, "reason": body.reason},
    })
    return {"kill_switch": body.enabled, "reason": body.reason}


@router.get("/kill-switch")
def get_kill_switch(
    request: Request,
    user: dict = Depends(require_role([UserRole.admin.value])),
) -> Dict[str, Any]:
    """Current kill-switch status (admin only)."""
    return {"kill_switch": bool(getattr(request.app.state, "kill_switch", False))}
