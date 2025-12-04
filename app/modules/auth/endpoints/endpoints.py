from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.database import get_db_session
from app.core.security import (create_access_token, create_refresh_token, decode_token)
from app.config import settings
from app.modules.auth.services.auth_service import authenticate_user, create_user, get_current_active_user, oauth2_scheme
from app.modules.auth.db.repository import AuthRepository, TokenBlocklistRepository
from app.modules.auth.db.schema import User as SQLUser
from app.modules.auth.models.pydantic_models import (User, UserCreate, Token,
                                                    UserProfileUpdate, ForgotPasswordRequest,
                                                    ResetPasswordRequest)

router = APIRouter()

@router.post("/token", response_model=Token, tags=["Authentication"])
def login_for_access_token(
    db: Session = Depends(get_db_session),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Authenticates a user and returns a JWT token.
    Corresponds to /api/auth/login from PRD.
    """
    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password, or inactive account",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def register_user(user: UserCreate, db: Session = Depends(get_db_session)):
    """
    Creates a new user.
    Corresponds to /api/auth/register from PRD.
    """
    auth_repo = AuthRepository(db)
    db_user = auth_repo.get_by_email(email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    try:
        return create_user(db=db, user=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refresh-token", response_model=Token, tags=["Authentication"])
def refresh_token(
    db: Session = Depends(get_db_session),
    authorization: str = Header(...)
):
    """Provides a new access token from a valid refresh token."""
    token_type, _, token = authorization.partition(' ')
    if token_type.lower() != 'bearer' or not token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    auth_repo = AuthRepository(db)
    user = auth_repo.get_by_email(payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout", tags=["Authentication"])
def logout(
    db: Session = Depends(get_db_session),
    token: str = Depends(oauth2_scheme)
):
    """Invalidates the current user's token."""
    payload = decode_token(token)
    if payload:
        jti = payload.get("jti")
        if jti:
            blocklist_repo = TokenBlocklistRepository(db)
            blocklist_repo.add_to_blocklist(jti)
    return {"message": "Successfully logged out"}

@router.get("/users/me", response_model=User, tags=["Authentication - Users"])
def read_users_me(current_user: SQLUser = Depends(get_current_active_user)):
    """Gets the profile of the currently authenticated user."""
    return current_user

@router.put("/users/me", response_model=User, tags=["Authentication - Users"])
def update_users_me(
    user_update: UserProfileUpdate,
    db: Session = Depends(get_db_session),
    current_user: SQLUser = Depends(get_current_active_user)
):
    """Updates the profile of the currently authenticated user."""
    auth_repo = AuthRepository(db)
    return auth_repo.update(current_user, user_update)

@router.post("/forgot-password", tags=["Authentication"])
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db_session)):
    """Initiates the password reset process."""
    auth_repo = AuthRepository(db)
    user = auth_repo.get_by_email(request.email)
    if not user:
        # Do not reveal that the user does not exist
        return {"message": "If an account with that email exists, a password reset link has been sent."}

    # In a real application, you would generate a secure, single-use token,
    # save it, and email it to the user.
    reset_token = create_access_token(data={"sub": user.email}, expires_delta=timedelta(minutes=15))
    print(f"Password reset token for {user.email}: {reset_token}") # Simulate sending email
    return {"message": "Password reset link has been sent."}

@router.post("/reset-password", tags=["Authentication"])
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db_session)):
    """Resets the user's password using a valid token."""
    payload = decode_token(request.token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    auth_repo = AuthRepository(db)
    user = auth_repo.get_by_email(payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    auth_repo.update_password(user, request.new_password)
    return {"message": "Password has been successfully reset."}
