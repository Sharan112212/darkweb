from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional, List, Dict, Any
from cases.case_manager import CaseManager, Case
from api.rbac import ROLE_HIERARCHY

router = APIRouter(prefix="/v1/cases", tags=["Cases"])

# Global case manager singleton for API layer
case_manager = CaseManager()

def verify_role(user_role: str, min_role: str):
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    min_level = ROLE_HIERARCHY.get(min_role, 99)
    if user_level < min_level:
        raise HTTPException(status_code=403, detail=f"Forbidden: Role '{user_role}' lacks required permissions (minimum: '{min_role}').")

@router.post("", response_model=Dict[str, Any])
def create_case(
    payload: Dict[str, Any],
    x_user_role: str = Header("analyst", alias="X-User-Role"),
    x_user_id: str = Header("analyst_1", alias="X-User-Id")
):
    verify_role(x_user_role, min_role="analyst")
    name = payload.get("name")
    description = payload.get("description", "")
    if not name:
        raise HTTPException(status_code=400, detail="Field 'name' is required.")

    case = case_manager.create_case(
        name=name,
        description=description,
        created_by=x_user_id,
        actor_ids=payload.get("actor_ids", []),
        link_ids=payload.get("link_ids", []),
        evidence_ids=payload.get("evidence_ids", [])
    )
    return case.model_dump()

@router.get("", response_model=List[Dict[str, Any]])
def list_cases(
    x_user_role: str = Header("viewer", alias="X-User-Role"),
    created_by: Optional[str] = Query(None)
):
    verify_role(x_user_role, min_role="viewer")
    cases = case_manager.list_cases(created_by=created_by)
    return [c.model_dump() for c in cases]

@router.get("/{case_id}", response_model=Dict[str, Any])
def get_case(
    case_id: str,
    x_user_role: str = Header("viewer", alias="X-User-Role")
):
    verify_role(x_user_role, min_role="viewer")
    case = case_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return case.model_dump()

@router.post("/{case_id}/notes", response_model=Dict[str, Any])
def add_case_note(
    case_id: str,
    payload: Dict[str, Any],
    x_user_role: str = Header("analyst", alias="X-User-Role"),
    x_user_id: str = Header("analyst_1", alias="X-User-Id")
):
    verify_role(x_user_role, min_role="analyst")
    text = payload.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Field 'text' is required.")

    try:
        case = case_manager.add_note(case_id=case_id, author=x_user_id, text=text)
        return case.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{case_id}/legal-hold", response_model=Dict[str, Any])
def set_legal_hold(
    case_id: str,
    payload: Dict[str, Any],
    x_user_role: str = Header("reviewer", alias="X-User-Role"),
    x_user_id: str = Header("reviewer_1", alias="X-User-Id")
):
    verify_role(x_user_role, min_role="reviewer")
    hold_status = payload.get("legal_hold", True)
    try:
        case = case_manager.set_legal_hold(case_id=case_id, hold_status=hold_status, updated_by=x_user_id)
        return case.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
