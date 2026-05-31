import logging
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import User

logger = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_BILLING_STAFF = "billing_staff"
ROLE_VIEWER = "viewer"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_BILLING_STAFF, ROLE_VIEWER}
READ_ROLES = (ROLE_ADMIN, ROLE_BILLING_STAFF, ROLE_VIEWER)
WRITE_ROLES = (ROLE_ADMIN, ROLE_BILLING_STAFF)
ADMIN_ROLES = (ROLE_ADMIN,)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == normalize_email(email)).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user_access_token(user: User) -> str:
    return create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        }
    )


def get_current_user(request: Request) -> dict:
    current_user = getattr(request.state, "user", None)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_roles(*allowed_roles: str):
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions",
            )
        return current_user

    return dependency


def bootstrap_admin_user(db: Session) -> None:
    email = normalize_email(settings.BOOTSTRAP_ADMIN_EMAIL or "")
    password = settings.BOOTSTRAP_ADMIN_PASSWORD or ""
    if not email or not password:
        logger.warning("Bootstrap admin skipped: BOOTSTRAP_ADMIN_EMAIL or BOOTSTRAP_ADMIN_PASSWORD is unset.")
        return

    full_name = settings.BOOTSTRAP_ADMIN_NAME or "Bootstrap Admin"
    sync_from_env = settings.BOOTSTRAP_ADMIN_SYNC_FROM_ENV
    env_user = db.query(User).filter(User.email == email).first()
    existing_admin = db.query(User).filter(User.role == ROLE_ADMIN).first()
    if env_user:
        if sync_from_env or not existing_admin:
            env_user.full_name = full_name
            env_user.role = ROLE_ADMIN
            env_user.is_active = True
            if sync_from_env:
                env_user.hashed_password = get_password_hash(password)
            db.commit()
            logger.info("Bootstrap admin user synchronized from environment configuration.")
        return

    if existing_admin and not sync_from_env:
        return

    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password),
        role=ROLE_ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    logger.info("Bootstrap admin user created from environment configuration.")
