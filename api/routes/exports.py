from fastapi import APIRouter, HTTPException, Header, Response, Query
from typing import Optional, Dict, Any
from export.exporter import ExportEngine, ExportSnapshot
from api.rbac import ROLE_HIERARCHY

router = APIRouter(prefix="/v1/exports", tags=["Exports"])

export_engine = ExportEngine()
snapshots_store: Dict[str, ExportSnapshot] = {}

def verify_role(user_role: str, min_role: str):
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    min_level = ROLE_HIERARCHY.get(min_role, 99)
    if user_level < min_level:
        raise HTTPException(status_code=403, detail=f"Forbidden: Role '{user_role}' lacks required permissions (minimum: '{min_role}').")

@router.post("", response_model=Dict[str, Any])
def create_export(
    payload: Dict[str, Any],
    x_user_role: str = Header("analyst", alias="X-User-Role"),
    x_user_id: str = Header("analyst_1", alias="X-User-Id")
):
    verify_role(x_user_role, min_role="analyst")
    actors = payload.get("actors", [])
    candidate_links = payload.get("candidate_links", [])
    evidence_units = payload.get("evidence_units", [])
    case_id = payload.get("case_id")
    limitations = payload.get("limitations", [])

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

@router.get("/{export_id}", response_model=Dict[str, Any])
def get_export(
    export_id: str,
    x_user_role: str = Header("viewer", alias="X-User-Role")
):
    verify_role(x_user_role, min_role="viewer")
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
