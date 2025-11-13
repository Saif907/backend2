from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.libs.config import settings
from app.libs.supabase_client import supabase_client
# REMOVED: from app.auth.models import TokenData
import requests

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token scheme
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


# REMOVED: create_access_token function


# REMOVED: decode_access_token function


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user from Supabase token"""
    token = credentials.credentials
    
    print(f"🔐 Received token: {token[:50]}...")  # Debug log
    
    try:
        # Verify token with Supabase REST API
        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {token}"
        }
        
        print(f"📡 Calling Supabase API: {settings.SUPABASE_URL}/auth/v1/user")  # Debug log
        
        response = requests.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers=headers
        )
        
        print(f"✅ Supabase response status: {response.status_code}")  # Debug log
        
        if response.status_code == 200:
            user_data = response.json()
            user_id = user_data.get("id")
            email = user_data.get("email")
            
            print(f"👤 User ID: {user_id}")  # Debug log
            
            if user_id:
                # Try to get profile
                try:
                    # Try to select existing profile
                    profile = supabase_client.service_client.table("profiles")\
                        .select("*")\
                        .eq("id", user_id)\
                        .execute()
                    
                    if profile.data and len(profile.data) > 0:
                        print(f"✅ Profile found")
                        return profile.data[0]
                    
                    # Profile doesn't exist - return minimal user data
                    # The profile should be created by a database trigger on auth.users insert
                    print(f"⚠️ Profile not found, returning minimal user data")
                    return {
                        "id": user_id,
                        "pseudonymous_id": user_id,
                        "consent_given": True
                    }
                
                except Exception as profile_error:
                    print(f"❌ Profile error: {profile_error}")
                    # Return basic user info
                    return {
                        "id": user_id,
                        "pseudonymous_id": user_id,
                        "consent_given": True
                    }
        else:
            print(f"❌ Supabase error response: {response.text}")  # Debug log
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Get current active user (can add additional checks here)"""
    return current_user