from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import (
    authenticate_user,
    create_user_access_token,
    get_client_ip,
    get_current_user,
)
from app.core.config import settings
from app.db.database import get_db
from app.models import User
from app.schemas.auth import LoginRequest, LogoutResponse, TokenResponse, UserResponse
from app.utils.audit import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = datetime.utcnow()
    db.commit()

    log_audit(
        db=db,
        action="user_login",
        user_id=user.id,
        details={"role": user.role},
        ip_address=get_client_ip(request),
    )

    return TokenResponse(
        access_token=create_user_access_token(user),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive or no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log_audit(
        db=db,
        action="user_logout",
        user_id=current_user["id"],
        details={"role": current_user.get("role")},
        ip_address=get_client_ip(request),
    )
    return LogoutResponse(message="Logged out")
