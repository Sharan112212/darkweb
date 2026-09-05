import os
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.enums import UserRole

JWT_SECRET = os.environ.get("JWT_SECRET", "sih26151_jwt_dev_secret_key_change_in_prod")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

security_scheme = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {
    UserRole.viewer.value: 1,
    UserRole.analyst.value: 2,
    UserRole.reviewer.value: 3,
    UserRole.admin.value: 4,
}

def create_jwt_token(user_id: str, role: str, expires_in_hours: int = TOKEN_EXPIRE_HOURS) -> str:
    """Generates a signed JWT access token for user_id and role."""
    if role not in ROLE_HIERARCHY:
        raise ValueError(f"Invalid role: {role}. Must be one of {list(ROLE_HIERARCHY.keys())}")
    
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=expires_in_hours)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> Dict[str, Any]:
    """FastAPI dependency: Extracts user payload from Authorization Bearer header."""
    if not credentials or not credentials.credentials:
        # Default anonymous/system fallback if no token provided in test environment
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer header")
    
    return decode_jwt_token(credentials.credentials)

def require_role(allowed_roles: List[str]):
    """
    FastAPI security dependency factory: Enforces RBAC permissions.
    Allows user if user role is in allowed_roles or has higher hierarchy precedence.
    """
    def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = user.get("role", UserRole.viewer.value)
        user_level = ROLE_HIERARCHY.get(user_role, 0)

        min_required_level = min(ROLE_HIERARCHY.get(r, 99) for r in allowed_roles)
        
        if user_level < min_required_level and user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Role '{user_role}' lacks required permissions ({allowed_roles})"
            )
        return user

    return role_checker
