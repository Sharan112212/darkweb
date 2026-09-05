from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from fusion.link_lifecycle import LinkLifecycleManager
from db.repositories.link_repo import LinkRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/links", tags=["Candidate Links"])

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

class TransitionRequest(BaseModel):
    target_state: str
    reason: str

@router.get("")
def list_links(
    request: Request,
    state: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Lists candidate links with optional state or tier filter."""
    repo = LinkRepository(db_path)
    links = repo.list_all()

    if state:
        links = [l for l in links if l.get("state") == state]
    if tier:
        links = [l for l in links if l.get("tier") == tier]

    return links[:limit]

@router.get("/{link_id}")
def get_link(
    link_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Retrieves specific candidate link details."""
    repo = LinkRepository(db_path)
    link = repo.get_by_id(link_id)
    if not link:
        raise HTTPException(status_code=404, detail=f"Candidate link '{link_id}' not found")
    return link

@router.post("/{link_id}/transition")
def transition_link(
    link_id: str,
    req: TransitionRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.analyst.value, UserRole.reviewer.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """
    Executes link state machine transition (e.g. proposed -> needs_review -> accepted / rejected).
    Persists new version in candidate_link_versions table with analyst ID and reason.
    """
    manager = LinkLifecycleManager(db_path=db_path)
    user_id = user.get("sub", "analyst_unknown")
    try:
        updated_link = manager.transition_state(
            link=link_id,
            new_state=req.target_state,
            changed_by=user_id,
            reason=req.reason
        )
        return updated_link.model_dump() if hasattr(updated_link, "model_dump") else updated_link
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to transition link state: {exc}")

@router.get("/{link_id}/history")
def get_link_history(
    link_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Returns full version history for candidate link."""
    repo = LinkRepository(db_path)
    history = repo.get_versions(link_id)
    return history
