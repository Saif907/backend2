from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserSignUp(BaseModel):
    """User registration data"""
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserSignIn(BaseModel):
    """User login credentials"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT access token response"""
    access_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None


class TokenData(BaseModel):
    """Data stored in JWT token"""
    user_id: str
    email: Optional[str] = None


class UserProfile(BaseModel):
    """User profile data"""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserResponse(BaseModel):
    """User response with profile data"""
    user: UserProfile
    session: Optional[dict] = None