from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
import uuid

# --- User Schemas ---

class UserBase(BaseModel):
    """Base Pydantic model for User."""
    email: EmailStr
    full_name: str
    employee_id: str
    mobile_number: str
    designation: str
    department: str

class UserCreate(UserBase):
    """Pydantic model for creating a new user."""
    password: str

class User(UserBase):
    """Pydantic model for returning a user (response)."""
    id: uuid.UUID
    role: str
    account_status: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

# --- Token Schemas ---

class Token(BaseModel):
    """Pydantic model for the JWT token response."""
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None

class UserProfileUpdate(BaseModel):
    """Pydantic model for updating a user's profile."""
    full_name: Optional[str] = None
    mobile_number: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    profile_picture_url: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

