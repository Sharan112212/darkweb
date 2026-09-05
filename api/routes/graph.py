from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from graph.neo4j_projection import Neo4jProjection
from graph.networkx_projection import NetworkXProjection
from graph.path_finder import PathFinder
from graph.reconciliation import GraphReconciliationEngine
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/graph", tags=["Graph & Multi-Hop Attribution"])

def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)

class PathSearchRequest(BaseModel):
    source_entity_id: str
    target_entity_id: str
    max_hops: int = Field(4, ge=1, le=10)
    min_score: float = Field(0.0, ge=0.0, le=1.0)

@router.get("/projection")
def get_graph_projection(
    request: Request,
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Returns node and edge graph projection JSON."""
    proj = Neo4jProjection()
    proj.sync_from_db(db_path=db_path, min_score=min_score)
    return proj.get_projection()

@router.get("/paths")
def search_attribution_paths_get(
    request: Request,
    source_entity_id: str = Query(...),
    target_entity_id: str = Query(...),
    max_hops: int = Query(4, ge=1, le=10),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Finds multi-hop attribution paths between source and target entities (GET)."""
    proj = Neo4jProjection()
    proj.sync_from_db(db_path=db_path, min_score=min_score)
    finder = PathFinder(projection=proj)
    result = finder.find_attribution_paths(
        source_id=source_entity_id,
        target_id=target_entity_id,
        max_hops=max_hops,
        min_score=min_score
    )
    return result

@router.post("/paths")
def search_attribution_paths_post(
    req: PathSearchRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Finds multi-hop attribution paths between source and target entities (POST)."""
    proj = Neo4jProjection()
    proj.sync_from_db(db_path=db_path, min_score=req.min_score)
    finder = PathFinder(projection=proj)
    result = finder.find_attribution_paths(
        source_id=req.source_entity_id,
        target_id=req.target_entity_id,
        max_hops=req.max_hops,
        min_score=req.min_score
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
    proj = Neo4jProjection()
    count = proj.sync_from_db(db_path=db_path, min_score=min_score)
    return {
        "status": "success",
        "synced_edges": count,
        "projection": proj.get_projection()
    }

@router.post("/reconcile")
def reconcile_graph_projection(
    request: Request,
    user: dict = Depends(require_role([UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Reconciles canonical database against graph projection (Admin only — EC-32)."""
    engine = GraphReconciliationEngine(db_path=db_path)
    engine.backfill()
    return engine.reconcile()

@router.post("/backfill")
def backfill_graph_projection(
    request: Request,
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    user: dict = Depends(require_role([UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Backfills canonical database records into graph projection (Admin only — EC-32)."""
    engine = GraphReconciliationEngine(db_path=db_path)
    return engine.backfill(min_score=min_score)

@router.post("/rollback")
def rollback_graph_projection(
    request: Request,
    user: dict = Depends(require_role([UserRole.admin.value])),
    db_path: Optional[str] = Depends(get_db_path)
):
    """Rolls back and resynchronizes graph projection from canonical database (Admin only — EC-32)."""
    engine = GraphReconciliationEngine(db_path=db_path)
    return engine.rollback()

