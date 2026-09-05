from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from api.rbac import create_jwt_token, get_current_user, UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])

class TokenRequest(BaseModel):
    username: str
    password: Optional[str] = "demo_password"
    role: Optional[str] = UserRole.analyst.value

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str

@router.post("/token", response_model=TokenResponse)
def login_for_access_token(req: TokenRequest):
    """Generates signed JWT token for requesting user and role."""
    if not req.username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    role = req.role or UserRole.analyst.value
    if role not in [r.value for r in UserRole]:
        raise HTTPException(status_code=400, detail=f"Invalid role '{role}'")

    token = create_jwt_token(user_id=req.username, role=role)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=req.username,
        role=role
    )

@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    """Returns currently authenticated user profile."""
    return {
        "user_id": user.get("sub"),
        "role": user.get("role"),
        "issued_at": user.get("iat"),
        "expires_at": user.get("exp")
    }
