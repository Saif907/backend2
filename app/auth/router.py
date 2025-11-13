from fastapi import APIRouter, HTTPException, status, Depends
# REMOVED: from datetime import timedelta
# REMOVED: from app.auth.models import UserSignUp, UserSignIn, Token, UserResponse
# REMOVED: from app.auth.utils import get_password_hash, create_access_token
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client
# REMOVED: from app.libs.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ❌ REMOVED: sign_up route to avoid conflict with frontend SDK


# ❌ REMOVED: sign_in route to avoid conflict with frontend SDK


@router.post("/signout")
async def sign_out(current_user: dict = Depends(get_current_active_user)):
    """Sign out current user"""
    try:
        supabase_client.client.auth.sign_out()
        return {"message": "Successfully signed out"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=dict)
async def get_me(current_user: dict = Depends(get_current_active_user)):
    """Get current user profile"""
    return current_user


@router.get("/session")
async def get_session(current_user: dict = Depends(get_current_active_user)):
    """Get current session"""
    try:
        # Note: This returns the Supabase session object from the Python client.
        session = supabase_client.client.auth.get_session()
        return {"session": session}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session"
        )