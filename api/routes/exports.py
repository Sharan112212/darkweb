from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Query
from pydantic import BaseModel
from db.repositories.export_repo import ExportRepository, DISCLOSURE
from db.repositories.link_repo import LinkRepository
from db.repositories.audit_repo import AuditRepository
from export.exporter import ExportEngine, ExportSnapshot
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/exports", tags=["Exports"])

export_engine = ExportEngine()
snapshots_store: Dict[str, ExportSnapshot] = {}

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

class ExportRequest(BaseModel):
    export_type: str = "links"
    entity_id: Optional[str] = None
    actors: List[Dict[str, Any]] = []
    candidate_links: List[Dict[str, Any]] = []
    evidence_units: List[Dict[str, Any]] = []
    case_id: Optional[str] = None
    limitations: List[str] = []

@router.post("")
def create_export(
    body: ExportRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    requester = user.get("sub", "analyst_unknown")
    user_role = user.get("role", "analyst")

    if db_path:
        links = LinkRepository(db_path).list_all(limit=10000)
        if body.entity_id:
            links = [l for l in links if l.get("left_entity_id") == body.entity_id or l.get("right_entity_id") == body.entity_id]

        repo = ExportRepository(db_path)
        export_dict = repo.create_export({
            "export_type": body.export_type,
            "requested_by": requester,
            "scope": {"entity_id": body.entity_id},
            "snapshot": {"links": links, "link_count": len(links)},
        })
        AuditRepository(db_path).append({
            "user_id": requester, "action": "export_created", "object_id": export_dict["export_id"],
            "details": {"export_type": body.export_type, "link_count": len(links)},
        })
        return export_dict

    snapshot = export_engine.create_snapshot(
        generated_by=requester,
        user_role=user_role,
        actors=body.actors,
        candidate_links=body.candidate_links,
        evidence_units=body.evidence_units,
        case_id=body.case_id,
        limitations=body.limitations
    )
    snapshots_store[snapshot.export_id] = snapshot

    out = snapshot.model_dump()
    out["snapshot_sha256"] = snapshot.calculation_input_hash
    return out

@router.get("")
def list_exports(
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value, UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> List[Dict[str, Any]]:
    if db_path:
        return ExportRepository(db_path).list_all(limit=200)
    return [s.model_dump() for s in snapshots_store.values()]

@router.get("/{export_id}")
def get_export(
    export_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value, UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    if db_path:
        repo = ExportRepository(db_path)
        export_item = repo.get_by_id(export_id)
        if not export_item:
            raise HTTPException(status_code=404, detail=f"Export '{export_id}' not found")
        return export_item

    snapshot = snapshots_store.get(export_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Export '{export_id}' not found")

    out = snapshot.model_dump()
    out["snapshot_sha256"] = snapshot.calculation_input_hash
    return out

@router.get("/{export_id}/download")
def download_export(
    export_id: str,
    format: str = Query("json", pattern="^(json|csv|pdf)$"),
    user: dict = Depends(require_role([UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value]))
):
    snapshot = snapshots_store.get(export_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Export snapshot '{export_id}' not found.")

    if format == "json":
        content = export_engine.render_json(snapshot)
        return Response(content=content, media_type="application/json", headers={"Content-Disposition": f"attachment; filename={export_id}.json"})
    elif format == "csv":
        content = export_engine.render_csv(snapshot)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={export_id}.csv"})
    elif format == "pdf":
        pdf_bytes = export_engine.render_pdf(snapshot)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={export_id}.pdf"})
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{format}'.")
