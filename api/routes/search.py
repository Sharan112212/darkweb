from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from db.repositories.entity_repo import EntityRepository
from api.rbac import require_role, UserRole

router = APIRouter(prefix="/search", tags=["Search"])


def get_db_path(request: Request) -> Optional[str]:
    return getattr(request.app.state, "db_path", None)


class SearchRequest(BaseModel):
    query: str = ""
    entity_type: Optional[str] = None
    limit: int = 50
    offset: int = 0


@router.post("")
def search_entities(
    body: SearchRequest,
    request: Request,
    user: dict = Depends(require_role([UserRole.viewer.value])),
    db_path: Optional[str] = Depends(get_db_path),
) -> Dict[str, Any]:
    """
    Search entities by (normalized) name substring. Returns an explicit
    availability/absence state rather than a bare empty list (EC-39), and always
    paginates.
    """
    repo = EntityRepository(db_path)
    entities = repo.list_all(limit=10000)

    q = (body.query or "").strip().lower()
    matched = []
    for e in entities:
        if body.entity_type and e.get("entity_type") != body.entity_type:
            continue
        hay = " ".join(str(e.get(k, "")).lower() for k in ("canonical_name", "normalized_name", "display_name", "entity_id"))
        if not q or q in hay:
            matched.append(e)

    total = len(matched)
    limit = max(1, min(body.limit, 500))
    offset = max(0, body.offset)
    page = matched[offset: offset + limit]
    truncated = (offset + limit) < total

    if total == 0:
        reason = "no_entities_collected" if not entities else "no_matching_evidence"
        return {"results": [], "total": 0, "returned": 0, "truncated": False,
                "absence_reason": reason, "query": body.query}

    return {"results": page, "total": total, "returned": len(page),
            "truncated": truncated, "query": body.query,
            "filters": {"entity_type": body.entity_type, "limit": limit, "offset": offset}}
