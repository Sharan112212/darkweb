from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from collection.capture_manager import CaptureManager
from db.repositories.capture_repo import CaptureRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/captures", tags=["Captures"])

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

class IngestRequest(BaseModel):
    source_id: str
    url: str
    raw_content: Optional[str] = None
    http_status: Optional[int] = 200
    content_type: Optional[str] = "text/html"

@router.post("", status_code=201)
def create_capture(
    req: IngestRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Ingests raw artifact content and records a Capture record."""
    mgr = CaptureManager(db_path=db_path)
    raw_bytes = req.raw_content.encode("utf-8") if req.raw_content else b"<html><body>Fixture</body></html>"
    capture = mgr.create_capture(
        source_id=req.source_id,
        url=req.url,
        raw_content_bytes=raw_bytes,
        http_status=req.http_status or 200,
        content_type=req.content_type or "text/html"
    )
    return capture.model_dump() if hasattr(capture, "model_dump") else capture

@router.get("")
def list_captures(
    request: Request,
    source_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Lists capture records."""
    repo = CaptureRepository(db_path)
    if source_id:
        return repo.list_by_source(source_id=source_id, limit=limit)
    return repo.list_all(limit=limit)

@router.get("/{capture_id}")
def get_capture(
    capture_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Retrieves a specific capture record by capture_id."""
    repo = CaptureRepository(db_path)
    cap = repo.get_by_id(capture_id)
    if not cap:
        raise HTTPException(status_code=404, detail=f"Capture '{capture_id}' not found")
    return cap
