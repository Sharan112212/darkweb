from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from db.repositories.case_repo import CaseRepository
from db.repositories.audit_repo import AuditRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/cases", tags=["Case Management"])


def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)


class CaseCreateRequest(BaseModel):
    title: str
    description: str = ""
    link_ids: List[str] = []
    entity_ids: List[str] = []


class NoteRequest(BaseModel):
    text: str


@router.post("")
def create_case(
    body: CaseCreateRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """Create an analyst case (analyst+). Audited."""
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Case title is required")
    repo = CaseRepository(db_path)
    owner = user.get("sub", "analyst_unknown")
    case = repo.create_case({
        "title": body.title, "description": body.description,
        "owner": owner, "link_ids": body.link_ids, "entity_ids": body.entity_ids,
    })
    AuditRepository(db_path).append({
        "user_id": owner, "action": "case_created", "object_id": case["case_id"],
        "details": {"title": body.title},
    })
    return case


@router.get("")
def list_cases(
    request: Request,
    owner: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> List[Dict[str, Any]]:
    """List cases (optionally by owner)."""
    repo = CaseRepository(db_path)
    if owner:
        return repo.list_by_owner(owner, limit=limit)
    return repo.list_all(limit=limit)


@router.get("/{case_id}")
def get_case(
    case_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    repo = CaseRepository(db_path)
    case = repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return case


@router.post("/{case_id}/notes")
def add_case_note(
    case_id: str,
    body: NoteRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """Append a note to a case (analyst+). Note text is mandatory."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Note text is required")
    repo = CaseRepository(db_path)
    author = user.get("sub", "analyst_unknown")
    updated = repo.add_note(case_id, author=author, text=body.text)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    AuditRepository(db_path).append({
        "user_id": author, "action": "case_note_added", "object_id": case_id,
        "details": {"text": body.text[:200]},
    })
    return updated
