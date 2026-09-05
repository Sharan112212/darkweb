from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from db.repositories.entity_repo import EntityRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/entities", tags=["Entities"])


def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)


@router.get("")
def list_entities(
    request: Request,
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> List[Dict[str, Any]]:
    """List canonical entities, optionally filtered by type."""
    repo = EntityRepository(db_path)
    if entity_type:
        return repo.list_by_type(entity_type, limit=limit)
    return repo.list_all(limit=limit)


@router.get("/{entity_type}/{entity_id}")
def get_entity(
    entity_type: str,
    entity_id: str,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """Retrieve a canonical entity by type + id."""
    repo = EntityRepository(db_path)
    entity = repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    if entity.get("entity_type") and entity.get("entity_type") != entity_type:
        raise HTTPException(status_code=404,
                            detail=f"Entity '{entity_id}' is not of type '{entity_type}'")
    return entity
