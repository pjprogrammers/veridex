"""VERIDEX API - Authentication & Authorization

Provides JWT token creation/verification, password hashing, and the
``get_current_user`` dependency used across all protected routes.

The JWT carries the user's primary ``role`` string (for backward compat)
and the list of role names from the ``users -> user_roles -> roles``
graph.  Route-level guards can check ``required_role()`` or
``require_permission()`` as needed.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
security = HTTPBearer()

# Well-known RBAC role names (must match seed data)
ROLE_OFFICER = "OFFICER"
ROLE_SUPERVISOR = "SUPERVISOR"
ROLE_ADMIN = "ADMIN"
ROLE_AUDITOR = "AUDITOR"

ALL_ROLES = {ROLE_OFFICER, ROLE_SUPERVISOR, ROLE_ADMIN, ROLE_AUDITOR}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Return a lightweight user dict from the JWT.

    The returned dict contains:
      - user_id  (str UUID)
      - role     (legacy primary role string)
      - roles    (list of role names from the DB graph)
    """
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return {
        "user_id": user_id,
        "role": payload.get("role", "officer"),
        "roles": payload.get("roles", []),
    }


def require_role(*allowed: str):
    """FastAPI dependency factory that gates on the user's primary role."""

    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "").upper()
        if user_role not in {r.upper() for r in allowed}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not authorized for this action",
            )
        return current_user

    return _check


def require_permission(permission: str):
    """FastAPI dependency factory that checks a specific permission string
    against the user's RBAC roles (requires DB lookup)."""

    async def _check(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(_get_db_session),
    ) -> dict:
        from app.models.models import Role, user_roles  # noqa: F811

        user_uuid = uuid.UUID(current_user["user_id"])
        result = await db.execute(
            select(Role.name, Role.permissions)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user_uuid)
        )
        for row in result:
            perms = row.permissions or []
            if permission in perms:
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {permission}",
        )

    return _check


# Lazy import to avoid circular dependency at module level
def _get_db_session():
    from app.core.database import get_db
    return get_db()

