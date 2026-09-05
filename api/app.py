from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.audit_middleware import AuditMiddleware
from api.routes import auth_router, captures_router, evidence_router, links_router, health_router

def create_app(db_path: Optional[str] = None) -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="SIH26151 Dark-Web Threat Actor Attribution API",
        description="REST API with RBAC, Audit Trail, and Evidence Provenance Controls.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.db_path = db_path

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Audit Trail Middleware (EC-15, EC-16)
    app.add_middleware(AuditMiddleware, db_path=db_path)

    # Register Routers under /api/v1
    api_v1_prefix = "/api/v1"
    app.include_router(auth_router, prefix=api_v1_prefix)
    app.include_router(captures_router, prefix=api_v1_prefix)
    app.include_router(evidence_router, prefix=api_v1_prefix)
    app.include_router(links_router, prefix=api_v1_prefix)
    app.include_router(health_router, prefix=api_v1_prefix)

    return app

app = create_app()
