from fastapi import APIRouter, HTTPException, Header, Query, Request, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from cases.case_manager import CaseManager, Case
from api.rbac import ROLE_HIERARCHY, require_role, UserRole
from db.repositories.case_repo import CaseRepository
from db.repositories.audit_repo import AuditRepository

router = APIRouter(prefix="/cases", tags=["Cases"])

# Global case manager singleton for in-memory / fast API usage
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

@router.post("", response_model=Dict[str, Any])
def create_case(
    payload: Dict[str, Any],
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    x_user_id = user.get("sub", "analyst_unknown")
    name = payload.get("name") or payload.get("title")
    description = payload.get("description", "")
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Field 'name' or 'title' is required.")

    if db_path:
        repo = CaseRepository(db_path)
        case_dict = repo.create_case({
            "title": name,
            "description": description,
            "owner": x_user_id,
            "link_ids": payload.get("link_ids", []),
            "entity_ids": payload.get("entity_ids", payload.get("actor_ids", [])),
        })
        AuditRepository(db_path).append({
            "user_id": x_user_id, "action": "case_created", "object_id": case_dict["case_id"],
            "details": {"title": name},
        })
        return case_dict

    case = case_manager.create_case(
        name=name,
        description=description,
        created_by=x_user_id,
        actor_ids=payload.get("actor_ids", payload.get("entity_ids", [])),
        link_ids=payload.get("link_ids", []),
        evidence_ids=payload.get("evidence_ids", [])
    )
    return case.model_dump()

@router.get("", response_model=List[Dict[str, Any]])
def list_cases(
    request: Request,
    owner: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    if db_path:
        repo = CaseRepository(db_path)
        target_owner = owner or created_by
        if target_owner:
            return repo.list_by_owner(target_owner)
        return repo.list_all()

    cases = case_manager.list_cases(created_by=created_by or owner)
    return [c.model_dump() for c in cases]

@router.get("/{case_id}", response_model=Dict[str, Any])
def get_case(
    case_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    if db_path:
        repo = CaseRepository(db_path)
        c = repo.get_by_id(case_id)
        if not c:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
        return c

    case = case_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return case.model_dump()

@router.post("/{case_id}/notes", response_model=Dict[str, Any])
def add_case_note(
    case_id: str,
    payload: Dict[str, Any],
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    x_user_id = user.get("sub", "analyst_unknown")
    text = payload.get("text")
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Field 'text' is required.")

    if db_path:
        repo = CaseRepository(db_path)
        updated = repo.add_note(case_id, author=x_user_id, text=text)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
        AuditRepository(db_path).append({
            "user_id": x_user_id, "action": "case_note_added", "object_id": case_id,
            "details": {"text": text[:200]},
        })
        return updated

    try:
        case = case_manager.add_note(case_id=case_id, author=x_user_id, text=text)
        return case.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{case_id}/legal-hold", response_model=Dict[str, Any])
def set_legal_hold(
    case_id: str,
    payload: Dict[str, Any],
    user: dict = Depends(require_role([UserRole.reviewer.value])),
):
    x_user_id = user.get("sub", "reviewer_unknown")
    hold_status = payload.get("legal_hold", True)
    try:
        case = case_manager.set_legal_hold(case_id=case_id, hold_status=hold_status, updated_by=x_user_id)
        return case.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
