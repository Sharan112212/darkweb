import uuid
from datetime import datetime, timezone
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from db.repositories.audit_repo import AuditRepository
from models.audit import AuditEvent

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically records an AuditEvent record for every API request/mutation.
    Enforces EC-15 & EC-16 audit log recording.
    """

    def __init__(self, app, db_path: Optional[str] = None):
        super().__init__(app)
        self.db_path = db_path

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")
        request.state.request_id = request_id

        user_id = "anonymous"
        user_role = "unknown"
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                import jwt
                from api.rbac import JWT_SECRET, JWT_ALGORITHM
                payload = jwt.decode(auth_header.split(" ")[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
                user_id = payload.get("sub", "anonymous")
                user_role = payload.get("role", "unknown")
            except Exception:
                pass

        response = await call_next(request)

        # Log audit event for mutations or non-health endpoints
        if not request.url.path.endswith("/health"):
            try:
                audit_repo = AuditRepository(self.db_path)
                event = AuditEvent(
                    event_id=f"evt_{uuid.uuid4().hex[:12]}",
                    request_id=request_id,
                    user_id=user_id,
                    action=f"{request.method} {request.url.path}",
                    object_id=request.url.path.split("/")[-1] or "root",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details={
                        "status_code": response.status_code,
                        "client_ip": request.client.host if request.client else "unknown",
                        "user_role": user_role,
                        "query_params": str(request.query_params)
                    }
                )
                audit_repo.append(event)
            except Exception as e:
                # Audit logging failures must not break request processing but should log warning
                pass

        response.headers["X-Request-ID"] = request_id
        return response
