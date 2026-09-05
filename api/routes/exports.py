from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from db.repositories.export_repo import ExportRepository
from db.repositories.link_repo import LinkRepository
from db.repositories.audit_repo import AuditRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/exports", tags=["Exports"])


def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)


class ExportRequest(BaseModel):
    export_type: str = "links"
    entity_id: Optional[str] = None  # if set, only links involving this entity


@router.post("")
def create_export(
    body: ExportRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """
    Create an immutable export snapshot of the current candidate links in scope.
    The snapshot is hashed and carries the mandatory disclosure, so a later data
    change never alters an already-created export (EC-15).
    """
    links = LinkRepository(db_path).list_all(limit=10000)
    if body.entity_id:
        links = [l for l in links
                 if l.get("left_entity_id") == body.entity_id or l.get("right_entity_id") == body.entity_id]

    repo = ExportRepository(db_path)
    requester = user.get("sub", "analyst_unknown")
    export = repo.create_export({
        "export_type": body.export_type,
        "requested_by": requester,
        "scope": {"entity_id": body.entity_id},
        "snapshot": {"links": links, "link_count": len(links)},
    })
    AuditRepository(db_path).append({
        "user_id": requester, "action": "export_created", "object_id": export["export_id"],
        "details": {"export_type": body.export_type, "link_count": len(links)},
    })
    return export


@router.get("/{export_id}")
def get_export(
    export_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    repo = ExportRepository(db_path)
    export = repo.get_by_id(export_id)
    if not export:
        raise HTTPException(status_code=404, detail=f"Export '{export_id}' not found")
    return export


@router.get("")
def list_exports(
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> List[Dict[str, Any]]:
    return ExportRepository(db_path).list_all(limit=200)
