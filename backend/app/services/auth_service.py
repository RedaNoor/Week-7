"""
Authentication & Authorization service for Real Estate Voice Agent (DB-backed).
"""

from __future__ import annotations

import os
import hashlib
import time
import uuid
import logging
from typing import Optional, Dict, Any

import jwt
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.user import User
from app.services.db_store_enhanced import get_session

logger = logging.getLogger("auth_service")
logger.setLevel(logging.INFO)

from datetime import datetime, timezone

# Config
JWT_SECRET = os.getenv("JWT_SECRET", "real-estate-agent-secret-key-2026-safe-default")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 86400 * 7  # 7 days

security_scheme = HTTPBearer(auto_error=False)

# Helper functions

def _hash_password(password: str, salt: str = "real_estate_salt_2026") -> str:
    """Hash password with SHA256 and salt."""
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()

def _init_default_users() -> None:
    """Seed default admin and client accounts if they do not exist in the DB."""
    session = get_session()
    if not session:
        logger.warning("Database session not available; cannot seed default users.")
        return
    try:
        admin_email = "admin@realestate.pk"
        client_email = "client@gmail.com"
        admin = session.query(User).filter(User.email == admin_email.lower()).first()
        client = session.query(User).filter(User.email == client_email.lower()).first()
        if not admin:
            admin = User(
                id=uuid.uuid4(),
                email=admin_email.lower(),
                name="System Admin",
                role="admin",
                hashed_password=_hash_password("admin123"),
                created_at=datetime.now(timezone.utc),
            )
            session.add(admin)
        if not client:
            client = User(
                id=uuid.uuid4(),
                email=client_email.lower(),
                name="Ridan Client",
                role="user",
                hashed_password=_hash_password("user123"),
                created_at=datetime.now(timezone.utc),
            )
            session.add(client)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed default users: {e}")
    finally:
        session.close()

# Ensure defaults are present at import time
_init_default_users()

def register_user(email: str, password: str, name: str, role: str = "user") -> Dict[str, Any]:
    """Register a new user in the database."""
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise ValueError("Invalid email address")
    if len(password) < 4:
        raise ValueError("Password must be at least 4 characters")
    session = get_session()
    if not session:
        raise ValueError("Database unavailable")
    try:
        existing = session.query(User).filter(User.email == email_clean).first()
        if existing:
            raise ValueError("User with this email already exists")
        role_clean = "admin" if role.lower() == "admin" else "user"
        user_id = uuid.uuid4()
        user_obj = User(
            id=user_id,
            email=email_clean,
            name=name.strip() or "Valued Client",
            role=role_clean,
            hashed_password=_hash_password(password),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(user_obj)
        session.commit()
        token = create_jwt_token(user_obj)
        return {
            "user": {
                "id": str(user_obj.id),
                "email": user_obj.email,
                "name": user_obj.name,
                "role": user_obj.role,
            },
            "token": token,
        }
    except Exception as e:
        session.rollback()
        raise ValueError(str(e))
    finally:
        session.close()

def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """Verify credentials and return JWT token."""
    email_clean = email.strip().lower()
    session = get_session()
    if not session:
        raise ValueError("Database unavailable")
    try:
        user = session.query(User).filter(User.email == email_clean).first()
        if not user or user.hashed_password != _hash_password(password):
            raise ValueError("Invalid email or password")
        token = create_jwt_token(user)
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
            },
            "token": token,
        }
    finally:
        session.close()

def create_jwt_token(user: Any) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRATION_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception as e:
        logger.debug(f"JWT decode error: {e}")
        return None

def get_current_user_optional(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_token: Optional[str] = Header(None, alias="X-User-Token"),
) -> Optional[Dict[str, Any]]:
    """Return decoded user payload if token valid, else None."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_user_token:
        token = x_user_token.strip()
    if not token:
        return None
    payload = decode_jwt_token(token)
    if not payload:
        return None
    # Verify user still exists in DB
    session = get_session()
    if not session:
        return payload
    try:
        user = session.query(User).filter(User.email == payload.get("email", "").lower()).first()
        if user:
            return {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role}
    except Exception as e:
        logger.warning(f"Error validating user session: {e}")
        return payload
    finally:
        session.close()
    return None

def get_current_user(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)) -> Dict[str, Any]:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

def require_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required.")
    return current_user
