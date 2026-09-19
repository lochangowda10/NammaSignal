"""
Authentication Endpoints
Login, logout, and token management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from apps.api.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    require_role,
    LoginRequest,
    LoginResponse,
    TokenData,
)
from domain.entities import Principal, RoleType

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """
    Authenticate user and return access token.
    In demo mode, accepts any credentials with special usernames:
    - 'citizen' -> Citizen role
    - 'responder' -> VerifiedResponder role
    - 'official' -> OfficialAuthority role
    """
    principal = authenticate_user(request.username, request.password)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(principal)
    return LoginResponse(
        access_token=access_token,
        expires_in=24 * 60 * 60,  # 24 hours in seconds
        user_info={
            "id": principal.id,
            "role": principal.role.value,
            "display_name": principal.display_name,
            "badge_number": principal.badge_number,
            "agency": principal.agency,
        },
    )


@router.post("/logout")
def logout():
    """
    Logout endpoint (client should discard token).
    In a more sophisticated implementation, we might maintain a token blacklist.
    """
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=Principal)
def get_current_user_info(current_user: Principal = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@router.get("/verify-token")
def verify_token_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Verify token validity"""
    try:
        token_data = TokenData(**jwt.decode(
            credentials.credentials,
            "your-secret-key-change-in-production",  # TODO: Move to config
            algorithms=["HS256"]
        ))
        return {"valid": True, "user_id": token_data.user_id}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Import jwt at the top to avoid circular import issues
import jwt