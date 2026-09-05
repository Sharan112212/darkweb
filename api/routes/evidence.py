from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from db.repositories.evidence_repo import EvidenceRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/evidence", tags=["Evidence Units"])

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

def _redact_sensitive_fields(unit: Dict[str, Any], user_role: str) -> Dict[str, Any]:
    """Redacts sensitive PII or unverified wallet/person attributes for viewer role (EC-16)."""
    if user_role == UserRole.viewer.value:
        cleaned = dict(unit)
        if "context_excerpt" in cleaned and cleaned["context_excerpt"]:
            cleaned["context_excerpt"] = "[REDACTED — VIEW ONLY PERMISSION]"
        return cleaned
    return unit

@router.get("")
def list_evidence(
    request: Request,
    left_entity_id: Optional[str] = Query(None),
    right_entity_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    indicator_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Lists evidence units with optional entity pair or indicator filter."""
    repo = EvidenceRepository(db_path)
    if left_entity_id and right_entity_id:
        units = repo.list_by_pair(left_entity_id, right_entity_id)
    else:
        units = repo.list_all()

    if category:
        units = [u for u in units if u.get("category") == category]
    if indicator_type:
        units = [u for u in units if u.get("indicator_type") == indicator_type]

    role = user.get("role", UserRole.viewer.value)
    return [_redact_sensitive_fields(u, role) for u in units[:limit]]

@router.get("/{evidence_id}")
def get_evidence(
    evidence_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Retrieves specific evidence unit by evidence_id."""
    repo = EvidenceRepository(db_path)
    unit = repo.get_by_id(evidence_id)
    if not unit:
        raise HTTPException(status_code=404, detail=f"Evidence unit '{evidence_id}' not found")
    
    role = user.get("role", UserRole.viewer.value)
    return _redact_sensitive_fields(unit, role)
