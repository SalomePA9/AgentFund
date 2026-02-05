"""
Authentication API endpoints.

Handles user registration, login, and session management.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from supabase import Client

from config import get_settings
from database import get_db

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response (excludes sensitive data)."""

    id: str
    email: str
    created_at: datetime
    settings: dict | None = None


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for decoded token data."""

    user_id: str | None = None


class UserSettings(BaseModel):
    """Schema for user settings update."""

    timezone: str | None = None
    report_time: str | None = None
    email_reports: bool | None = None
    email_alerts: bool | None = None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Client, Depends(get_db)],
) -> dict:
    """Get the current authenticated user from JWT token."""
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Fetch user from database
    result = db.table("users").select("*").eq("id", user_id).execute()

    if not result.data:
        raise credentials_exception

    return result.data[0]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: Annotated[Client, Depends(get_db)]):
    """Register a new user."""
    # Check if user already exists
    existing = db.table("users").select("id").eq("email", user.email).execute()

    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    hashed_password = get_password_hash(user.password)
    result = db.table("users").insert(
        {
            "email": user.email,
            "password_hash": hashed_password,
        }
    ).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

    return result.data[0]


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Client, Depends(get_db)],
):
    """Login and receive JWT token."""
    # Fetch user
    result = db.table("users").select("*").eq("email", form_data.username).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = result.data[0]

    # Verify password
    if not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create token
    access_token = create_access_token(data={"sub": user["id"]})

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout():
    """Logout (client should discard token)."""
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get current user information."""
    return current_user


@router.put("/settings", response_model=UserResponse)
async def update_settings(
    settings_update: UserSettings,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Update user settings."""
    current_settings = current_user.get("settings", {}) or {}

    # Merge with new settings
    update_data = settings_update.model_dump(exclude_none=True)
    new_settings = {**current_settings, **update_data}

    result = (
        db.table("users")
        .update({"settings": new_settings})
        .eq("id", current_user["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings",
        )

    return result.data[0]
