from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request, Header
from pydantic import BaseModel
from db.repositories.case_repo import CaseRepository
from db.repositories.audit_repo import AuditRepository
from cases.case_manager import CaseManager
from api.rbac import require_role, UserRole, ROLE_HIERARCHY

router = APIRouter(prefix="/cases", tags=["Case Management"])

# In-memory case manager for Branch 9 governance engine
case_manager = CaseManager()

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

class CaseCreateRequest(BaseModel):
    title: Optional[str] = None
    name: Optional[str] = None
    description: str = ""
    link_ids: List[str] = []
    entity_ids: List[str] = []
    actor_ids: List[str] = []
    evidence_ids: List[str] = []

class NoteRequest(BaseModel):
    text: str

@router.post("")
def create_case(
    body: CaseCreateRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """Create an analyst case (analyst+). Audited."""
    case_title = (body.title or body.name or "").strip()
    if not case_title:
        raise HTTPException(status_code=400, detail="Case title is required")

    owner = user.get("sub", "analyst_unknown")
    entity_list = list(set(body.entity_ids + body.actor_ids))

    # Sync with in-memory CaseManager
    case_obj = case_manager.create_case(
        name=case_title,
        description=body.description,
        created_by=owner,
        actor_ids=entity_list,
        link_ids=body.link_ids,
        evidence_ids=body.evidence_ids
    )

    if db_path:
        repo = CaseRepository(db_path)
        case_dict = repo.create_case({
            "case_id": case_obj.case_id,
            "title": case_title,
            "description": body.description,
            "owner": owner,
            "link_ids": body.link_ids,
            "entity_ids": entity_list,
        })
        AuditRepository(db_path).append({
            "user_id": owner, "action": "case_created", "object_id": case_dict["case_id"],
            "details": {"title": case_title},
        })
        return case_dict

    return case_obj.model_dump()

@router.get("")
def list_cases(
    request: Request,
    owner: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(require_role([UserRole.viewer.value, UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> List[Dict[str, Any]]:
    """List cases (optionally by owner)."""
    if db_path:
        repo = CaseRepository(db_path)
        if owner:
            return repo.list_by_owner(owner, limit=limit)
        return repo.list_all(limit=limit)

    cases = case_manager.list_cases(created_by=owner)
    return [c.model_dump() for c in cases]

@router.get("/{case_id}")
def get_case(
    case_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value, UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    if db_path:
        repo = CaseRepository(db_path)
        case = repo.get_by_id(case_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
        return case

    case = case_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return case.model_dump()

@router.post("/{case_id}/notes")
def add_case_note(
    case_id: str,
    body: NoteRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """Append a note to a case (analyst+). Note text is mandatory."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Note text is required")

    author = user.get("sub", "analyst_unknown")

    if db_path:
        repo = CaseRepository(db_path)
        updated = repo.add_note(case_id, author=author, text=body.text)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
        AuditRepository(db_path).append({
            "user_id": author, "action": "case_note_added", "object_id": case_id,
            "details": {"text": body.text[:200]},
        })
        return updated

    try:
        updated_case = case_manager.add_note(case_id, author=author, text=body.text)
        return updated_case.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{case_id}/legal-hold")
def set_legal_hold(
    case_id: str,
    payload: Dict[str, Any],
    request: Request,
    user: dict = Depends(require_role([UserRole.reviewer.value, UserRole.admin.value]))
) -> Dict[str, Any]:
    hold_status = payload.get("legal_hold", True)
    author = user.get("sub", "reviewer_1")
    try:
        updated_case = case_manager.set_legal_hold(case_id=case_id, hold_status=hold_status, updated_by=author)
        return updated_case.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
