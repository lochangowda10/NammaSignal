"""
NammaSignal Authentication System
JWT/OAuth2 implementation with role-based access control
"""
import os
import time
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from domain.entities import Principal, RoleType

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# Security bearer
security = HTTPBearer()


class TokenData(BaseModel):
    """JWT token payload"""
    user_id: str
    role: RoleType
    display_name: str
    exp: float


class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: Dict[str, Any]


def create_access_token(principal: Principal) -> str:
    """Create JWT access token for a principal"""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode = {
        "user_id": principal.id,
        "role": principal.role.value,
        "display_name": principal.display_name,
        "exp": expire.timestamp(),
        "iat": datetime.utcnow().timestamp(),
    }
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_data = TokenData(**payload)
        # Check if token is expired
        if token_data.exp < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token_data
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Principal:
    """Dependency to get current authenticated user"""
    token_data = verify_token(credentials.credentials)
    return Principal(
        id=token_data.user_id,
        role=RoleType(token_data.role),
        display_name=token_data.display_name,
    )


def require_role(required_role: RoleType):
    """Dependency factory for role-based access control"""
    def role_checker(current_user: Principal = Depends(get_current_user)) -> Principal:
        if current_user.role != required_role and current_user.role != RoleType.OFFICIAL_AUTHORITY:
            # Official authority can access everything
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}",
            )
        return current_user
    return role_checker


# Demo mode toggle for hackathon
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"


def demo_login(username: str, password: str) -> Optional[Principal]:
    """Demo authentication for hackathon - accepts any credentials in demo mode"""
    if not DEMO_MODE:
        return None

    # Demo users for different roles
    demo_users = {
        "citizen": Principal(
            id="citizen_demo_001",
            role=RoleType.CITIZEN,
            display_name="Demo Citizen",
            badge_number=None,
            agency=None
        ),
        "responder": Principal(
            id="responder_demo_001",
            role=RoleType.VERIFIED_RESPONDER,
            display_name="Demo Verified Responder",
            badge_number="VR-001",
            agency="BTP"
        ),
        "official": Principal(
            id="official_demo_001",
            role=RoleType.OFFICIAL_AUTHORITY,
            display_name="Demo Official Authority",
            badge_number="OFF-001",
            agency="BBMP"
        )
    }

    # Simple demo logic - in real implementation, validate against proper user store
    if username in demo_users:
        return demo_users[username]
    elif password == "demo":
        # Default to citizen if password is demo
        return demo_users["citizen"]

    return None


def authenticate_user(username: str, password: str) -> Optional[Principal]:
    """Authenticate user credentials"""
    # In demo mode, use demo authentication
    if DEMO_MODE:
        return demo_login(username, password)

    # TODO: Implement real authentication against user database
    # For now, return None to force demo mode in development
    return demo_login(username, password)