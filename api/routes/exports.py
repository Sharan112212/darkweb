from fastapi import APIRouter, HTTPException, Header, Response, Query, Request, Depends
from typing import Optional, List, Dict, Any
from export.exporter import ExportEngine, ExportSnapshot
from api.rbac import ROLE_HIERARCHY
from db.repositories.export_repo import ExportRepository
from db.repositories.link_repo import LinkRepository
from db.repositories.audit_repo import AuditRepository

router = APIRouter(prefix="/v1/exports", tags=["Exports"])

export_engine = ExportEngine()
snapshots_store: Dict[str, ExportSnapshot] = {}

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

def verify_role(user_role: str, min_role: str):
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    min_level = ROLE_HIERARCHY.get(min_role, 99)
    if user_level < min_level:
        raise HTTPException(status_code=403, detail=f"Forbidden: Role '{user_role}' lacks required permissions (minimum: '{min_role}').")

@router.post("", response_model=Dict[str, Any])
def create_export(
    payload: Dict[str, Any],
    request: Request,
    x_user_role: str = Header("analyst", alias="X-User-Role"),
    x_user_id: str = Header("analyst_1", alias="X-User-Id"),
    db_path: Optional[str] = Depends(get_db_path)
):
    verify_role(x_user_role, min_role="analyst")
    actors = payload.get("actors", [])
    candidate_links = payload.get("candidate_links", [])
    evidence_units = payload.get("evidence_units", [])
    case_id = payload.get("case_id")
    limitations = payload.get("limitations", [])

    if db_path and not candidate_links and not actors and not evidence_units:
        links = LinkRepository(db_path).list_all(limit=10000)
        entity_id = payload.get("entity_id") or (payload.get("scope", {}) if isinstance(payload.get("scope"), dict) else {}).get("entity_id")
        if entity_id:
            links = [l for l in links if l.get("left_entity_id") == entity_id or l.get("right_entity_id") == entity_id]
        repo = ExportRepository(db_path)
        export_dict = repo.create_export({
            "export_type": payload.get("export_type", "links"),
            "requested_by": x_user_id,
            "scope": {"entity_id": entity_id},
            "snapshot": {"links": links, "link_count": len(links)},
        })
        AuditRepository(db_path).append({
            "user_id": x_user_id, "action": "export_created", "object_id": export_dict["export_id"],
            "details": {"export_type": payload.get("export_type", "links"), "link_count": len(links)},
        })
        return export_dict

    snapshot = export_engine.create_snapshot(
        generated_by=x_user_id,
        user_role=x_user_role,
        actors=actors,
        candidate_links=candidate_links,
        evidence_units=evidence_units,
        case_id=case_id,
        limitations=limitations
    )
    snapshots_store[snapshot.export_id] = snapshot
    return snapshot.model_dump()

@router.get("", response_model=List[Dict[str, Any]])
def list_exports(
    request: Request,
    x_user_role: str = Header("viewer", alias="X-User-Role"),
    db_path: Optional[str] = Depends(get_db_path)
):
    verify_role(x_user_role, min_role="viewer")
    if db_path:
        return ExportRepository(db_path).list_all(limit=200)
    return [s.model_dump() for s in snapshots_store.values()]

@router.get("/{export_id}", response_model=Dict[str, Any])
def get_export(
    export_id: str,
    request: Request,
    x_user_role: str = Header("viewer", alias="X-User-Role"),
    db_path: Optional[str] = Depends(get_db_path)
):
    verify_role(x_user_role, min_role="viewer")
    if db_path:
        repo = ExportRepository(db_path)
        exp = repo.get_by_id(export_id)
        if exp:
            return exp

    snapshot = snapshots_store.get(export_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Export snapshot '{export_id}' not found.")
    return snapshot.model_dump()

@router.get("/{export_id}/download")
def download_export(
    export_id: str,
    format: str = Query("json", pattern="^(json|csv|pdf)$"),
    x_user_role: str = Header("analyst", alias="X-User-Role")
):
    verify_role(x_user_role, min_role="analyst")
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
