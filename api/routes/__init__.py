from api.routes.auth import router as auth_router
from api.routes.captures import router as captures_router
from api.routes.evidence import router as evidence_router
from api.routes.links import router as links_router
from api.routes.health import router as health_router
from api.routes.graph import router as graph_router
from api.routes.timeline import router as timeline_router
from api.routes.cases import router as cases_router
from api.routes.exports import router as exports_router
from api.routes.audit import router as audit_router

__all__ = [
    "auth_router",
    "captures_router",
    "evidence_router",
    "links_router",
    "health_router",
    "graph_router",
    "timeline_router",
    "cases_router",
    "exports_router",
    "audit_router",
]
