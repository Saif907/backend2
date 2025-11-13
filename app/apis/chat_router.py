from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.apis.models import (
    ChatCreate, ChatResponse, MessageCreate, 
    MessageResponse, ChatWithMessages
)
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client

router = APIRouter(prefix="/chats", tags=["Chats"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: ChatCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new chat session"""
    try:
        print(f"📝 Creating chat for user: {current_user.get('id')}")
        print(f"📝 Chat title: {chat_data.title}")
        
        # FIXED: Use service_client to bypass RLS
        response = supabase_client.service_client.table("chats").insert({
            "title": chat_data.title,
            "user_id": current_user["id"]
        }).execute()
        
        print(f"✅ Chat creation response: {response.data}")
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create chat"
            )
        
        return response.data[0]
    
    except Exception as e:
        print(f"❌ Error creating chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=List[ChatResponse])
async def get_chats(current_user: dict = Depends(get_current_active_user)):
    """Get all chats for current user"""
    try:
        # FIXED: Use service_client to bypass RLS
        response = supabase_client.service_client.table("chats")\
            .select("*")\
            .eq("user_id", current_user["id"])\
            .order("created_at", desc=True)\
            .execute()
        
        return response.data
    
    except Exception as e:
        print(f"❌ Error getting chats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{chat_id}", response_model=ChatWithMessages)
async def get_chat(
    chat_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get a specific chat with all messages"""
    try:
        # Get chat
        # FIXED: Use service_client to bypass RLS
        chat_response = supabase_client.service_client.table("chats")\
            .select("*")\
            .eq("id", chat_id)\
            .eq("user_id", current_user["id"])\
            .single()\
            .execute()
        
        if not chat_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        # Get messages
        # FIXED: Use service_client to bypass RLS
        messages_response = supabase_client.service_client.table("messages")\
            .select("*")\
            .eq("chat_id", chat_id)\
            .order("created_at", desc=False)\
            .execute()
        
        return {
            "chat": chat_response.data,
            "messages": messages_response.data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Delete a chat and all its messages"""
    try:
        # Verify ownership
        # FIXED: Use service_client to bypass RLS
        chat_response = supabase_client.service_client.table("chats")\
            .select("*")\
            .eq("id", chat_id)\
            .eq("user_id", current_user["id"])\
            .single()\
            .execute()
        
        if not chat_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        # Use service_client for DELETE operation
        supabase_client.service_client.table("chats")\
            .delete()\
            .eq("id", chat_id)\
            .execute()
        
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new message in a chat"""
    try:
        # Verify chat ownership
        # FIXED: Use service_client to bypass RLS
        chat_response = supabase_client.service_client.table("chats")\
            .select("*")\
            .eq("id", message_data.chat_id)\
            .eq("user_id", current_user["id"])\
            .single()\
            .execute()
        
        if not chat_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        # Use service_client for INSERT operation
        response = supabase_client.service_client.table("messages").insert({
            "chat_id": message_data.chat_id,
            "user_id": current_user["id"],
            "content": message_data.content,
            "role": message_data.role
        }).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create message"
            )
        
        return response.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )