from fastapi import APIRouter, HTTPException, status, Depends
# REMOVED: from datetime import timedelta
# REMOVED: from app.auth.models import UserSignUp, UserSignIn, Token, UserResponse
# REMOVED: from app.auth.utils import get_password_hash, create_access_token
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client
# REMOVED: from app.libs.config import settings
import asyncio # ADDED for concurrency

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- Helper Functions (Synchronous Wrappers for Blocking DB Calls) ---

def sign_out_sync():
    """Blocking function to sign out user."""
    # This must use the standard supabase client which handles the user's session
    supabase_client.client.auth.sign_out()

def get_session_sync():
    """Blocking function to get current session."""
    # This must use the standard supabase client which handles the user's session
    session = supabase_client.client.auth.get_session()
    # Check if the session is None, preventing immediate crash on unauthenticated call
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session"
        )
    return {"session": session}

# ---------------------------------------------------------------------


# ❌ REMOVED: sign_up route to avoid conflict with frontend SDK


# ❌ REMOVED: sign_in route to avoid conflict with frontend SDK


@router.post("/signout")
async def sign_out(current_user: dict = Depends(get_current_active_user)):
    """Sign out current user (Now non-blocking)"""
    try:
        # Use asyncio.to_thread to run the blocking operation safely
        await asyncio.to_thread(sign_out_sync)
        return {"message": "Successfully signed out"}
    
    except Exception as e:
        # The signout call itself may fail due to an invalid token format or connection issue
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=dict)
async def get_me(current_user: dict = Depends(get_current_active_user)):
    """
    Get current user profile.
    NOTE: This endpoint is already non-blocking because its dependency (get_current_active_user)
    is handled asynchronously (using httpx) and immediately returns the result here.
    """
    return current_user


@router.get("/session")
async def get_session(current_user: dict = Depends(get_current_active_user)):
    """Get current session (Now non-blocking)"""
    try:
        # Use asyncio.to_thread to run the blocking operation safely
        session_data = await asyncio.to_thread(get_session_sync)
        return session_data
    except HTTPException:
        # Pass through the 401 HTTPException raised in the helper if no session is found
        raise
    except Exception as e:
        print(f"❌ Error getting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not retrieve session"
        )