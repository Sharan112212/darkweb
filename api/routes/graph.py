from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from graph.networkx_projection import NetworkXProjection
from graph.path_finder import PathFinder
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/graph", tags=["Graph & Multi-Hop Attribution"])

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

@router.get("/projection")
def get_graph_projection(
    request: Request,
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Returns node and edge graph projection JSON."""
    proj = NetworkXProjection()
    proj.sync_from_db(db_path=db_path, min_score=min_score)
    return proj.get_projection()

@router.get("/paths")
def search_attribution_paths(
    request: Request,
    source_entity_id: str = Query(...),
    target_entity_id: str = Query(...),
    max_hops: int = Query(4, ge=1, le=10),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Finds multi-hop attribution paths between source and target entities."""
    proj = NetworkXProjection()
    proj.sync_from_db(db_path=db_path, min_score=min_score)
    finder = PathFinder(projection=proj)
    result = finder.find_attribution_paths(
        source_id=source_entity_id,
        target_id=target_entity_id,
        max_hops=max_hops,
        min_score=min_score
    )
    return result

@router.post("/sync")
def sync_graph_projection(
    request: Request,
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    user: dict = Depends(require_role([UserRole.analyst.value, UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Triggers graph projection re-sync from candidate links database."""
    proj = NetworkXProjection()
    count = proj.sync_from_db(db_path=db_path, min_score=min_score)
    return {
        "status": "success",
        "synced_edges": count,
        "projection": proj.get_projection()
    }
