from datetime import datetime, timezone
from fastapi import APIRouter
from db.connection import DatabaseConnection

router = APIRouter(prefix="/health", tags=["Health & Status"])

@router.get("")
def health_check():
    """System health check endpoint."""
    db_status = "healthy"
    try:
        conn = DatabaseConnection.get_instance()
        conn.execute("SELECT 1")
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "ok" if "unhealthy" not in db_status else "degraded",
        "service": "SIH26151 Dark-Web Attribution Platform API",
        "version": "1.0.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
