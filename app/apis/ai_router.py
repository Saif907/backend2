import asyncio
from fastapi import APIRouter, HTTPException, status, Depends
from app.apis.models import (
    AIMessageRequest, AIMessageResponse, 
    TradeExtractionRequest, AnalyticsRequest, AnalyticsResponse,
    TradeCreate, ChatResponse
)
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client
from app.libs.config import settings
import httpx 
import json
import traceback 

router = APIRouter(prefix="/ai", tags=["AI"])

# --- Helper Functions (DB-only logic remains here) ---

def calculate_profit_loss(entry_price, exit_price, quantity):
    """Calculates P&L. This financial logic stays local to the main backend."""
    if exit_price is not None:
        return (exit_price - entry_price) * quantity
    return None

def get_chat_and_trades_sync(chat_id, user_id):
    """DB READ: Fetches messages and trade history."""
    messages_response = supabase_client.service_client.table("messages")\
        .select("role, content")\
        .eq("chat_id", chat_id)\
        .order("created_at", desc=False)\
        .execute()
    trade_history_response = supabase_client.service_client.table("trades")\
        .select("ticker, entry_price, exit_price, quantity, entry_date, profit_loss, notes")\
        .eq("user_id", user_id)\
        .order("entry_date", desc=True)\
        .limit(20) \
        .execute()
    return messages_response.data, trade_history_response.data

def get_messages_for_title_sync(chat_id):
    """DB READ: Gets messages needed for title generation."""
    messages = supabase_client.service_client.table("messages")\
        .select("role, content")\
        .eq("chat_id", chat_id)\
        .order("created_at", desc=False)\
        .limit(4)\
        .execute()
    return messages.data

def insert_user_message_sync(chat_id, user_id, content):
    """DB WRITE: Saves user message."""
    return supabase_client.service_client.table("messages").insert({"chat_id": chat_id, "user_id": user_id, "content": content, "role": "user"}).execute()

def insert_ai_message_sync(chat_id, user_id, content):
    """DB WRITE: Saves AI message."""
    return supabase_client.service_client.table("messages").insert({"chat_id": chat_id, "user_id": user_id, "content": content, "role": "assistant"}).execute()
    
def insert_trade_sync(user_id, extracted_trade, profit_loss):
    """DB WRITE: Saves the new trade log."""
    return supabase_client.service_client.table("trades").insert({
        "user_id": user_id, "ticker": extracted_trade.ticker.upper(), "entry_date": extracted_trade.entry_date.isoformat(), 
        "entry_price": extracted_trade.entry_price, "quantity": extracted_trade.quantity, 
        "exit_date": extracted_trade.exit_date.isoformat() if extracted_trade.exit_date else None,
        "exit_price": extracted_trade.exit_price, "notes": extracted_trade.notes, "profit_loss": profit_loss
    }).execute()

# --- Proxy Router Endpoints ---

@router.post("/chat", response_model=AIMessageResponse)
async def ai_chat(request: AIMessageRequest, current_user: dict = Depends(get_current_active_user)):
    """PROXIES chat message to AI microservice for response/extraction/grounding."""
    user_id = current_user["id"]
    chat_id = request.chat_id
    
    try:
        # 1. Verify chat ownership (local DB access)
        chat_response = supabase_client.service_client.table("chats").select("id").eq("id", chat_id).eq("user_id", user_id).single().execute()
        if not chat_response.data: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        
        # 2. Concurrently execute initial I/O tasks
        user_msg_task = asyncio.to_thread(insert_user_message_sync, chat_id, user_id, request.message)
        db_read_task = asyncio.to_thread(get_chat_and_trades_sync, chat_id, user_id)
        
        (_, (messages_data, trade_history)) = await asyncio.gather(user_msg_task, db_read_task)

        # 3. Prepare Proxy Payload
        chat_history_for_ai = [{"role": m["role"], "content": m["content"]} for m in messages_data]
        ai_request_payload = {
            "user_message": request.message,
            "chat_history": chat_history_for_ai,
            "trade_history": trade_history
        }

        # 4. PROXY Call to AI Microservice for Conversation and Extraction
        async with httpx.AsyncClient(timeout=30) as client:
            ai_response = await client.post(f"{settings.AI_SERVICE_URL}/ai/process-chat", json=ai_request_payload)
        
        ai_response.raise_for_status() 

        # 5. Parse Response from Microservice
        ai_data = ai_response.json()
        neutral_ai_response_text = ai_data.get("message", "AI service error.")
        extracted_trade_dict = ai_data.get("trade_extracted")
        is_grounded_flag = ai_data.get("is_grounded", False) # Extract the grounding flag

        # Note: TradeCreate validation happens here on the proxy side
        extracted_trade = TradeCreate.model_validate(extracted_trade_dict) if extracted_trade_dict else None

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI Service Down or Failed: {e.response.status_code}")
    except Exception as e:
        # Fallback print for debugging unhandled errors
        print("❌ CRITICAL ERROR TRACEBACK in /ai/chat:")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Critical Error: {str(e)}")

    # 6. Save Final Data to DB (Supabase) and construct message
    trade_insert_task = None
    final_message_content = neutral_ai_response_text # Start with the AI's neutral response

    # === FIX: Prepend structural confirmation ONLY IF extraction succeeded ===
    if extracted_trade:
        # 6a. Calculate P&L and start DB save concurrently
        profit_loss_value = calculate_profit_loss(extracted_trade.entry_price, extracted_trade.exit_price, extracted_trade.quantity)
        trade_insert_task = asyncio.to_thread(insert_trade_sync, user_id, extracted_trade, profit_loss_value)
        
        # 6b. Construct the structural confirmation message
        confirmation_msg = f"**Acknowledged!** Your trade for **{extracted_trade.ticker}** has been logged.\n\n"
        
        # Format P&L for display in confirmation message
        if profit_loss_value is not None:
            # Determine status/color for confirmation
            pl_sign = "+" if profit_loss_value >= 0 else ""
            pl_color = "🟢" if profit_loss_value >= 0 else "🔴"
            pl_line = f"* **Profit/Loss:** {pl_color} ${pl_sign}{profit_loss_value:.2f}\n"
        else:
            pl_line = f"* **Status:** OPEN\n"

        confirmation_details = (
            f"* **Entry Price:** ${extracted_trade.entry_price}\n"
            f"* **Exit Price:** ${extracted_trade.exit_price or '-'}\n"
            f"* **Quantity:** {extracted_trade.quantity}\n"
            f"{pl_line}\n"
        )
        
        # Prepend the structural confirmation and details to the AI's neutral conversation.
        final_message_content = confirmation_msg + confirmation_details + neutral_ai_response_text
        
    # 6c. Save the final message content to the database
    ai_msg_task = asyncio.to_thread(insert_ai_message_sync, chat_id, user_id, final_message_content)
    
    await asyncio.gather(ai_msg_task, *([trade_insert_task] if trade_insert_task else []))
    
    # 7. Final response to Frontend
    return {
        "message": final_message_content,
        "trade_extracted": extracted_trade,
        "is_grounded": is_grounded_flag
    }

@router.post("/extract-trade")
async def extract_trade(request: TradeExtractionRequest, current_user: dict = Depends(get_current_active_user)):
    """PROXIES raw text extraction to the AI microservice."""
    try:
        # PROXY Call to AI Microservice
        async with httpx.AsyncClient(timeout=10) as client:
            ai_response = await client.post(f"{settings.AI_SERVICE_URL}/ai/extract-trade", json={"text": request.text})
            
        ai_response.raise_for_status()
        
        # Microservice returns TradeCreate JSON or null/empty body
        if ai_response.status_code == 200 and ai_response.text:
            return {"trade": TradeCreate.model_validate_json(ai_response.text), "message": "Trade extracted."}
        
        return {"trade": None, "message": "No trade information found in the text"}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI Service Down or Failed: {e.response.status_code}")
    except Exception as e:
        print("❌ CRITICAL ERROR TRACEBACK in /extract-trade:")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Critical Error: {str(e)}")


@router.get("/insights")
async def get_ai_insights(current_user: dict = Depends(get_current_active_user)):
    """PROXIES trade insights generation to AI microservice."""
    user_id = current_user["id"]
    try:
        # 1. Fetch data locally (Supabase)
        trades_response = supabase_client.service_client.table("trades")\
            .select("ticker, entry_price, exit_price, quantity, entry_date, profit_loss, notes")\
            .eq("user_id", user_id).order("entry_date", desc=True).limit(50).execute()
        
        # 2. Prepare Proxy Payload
        ai_request_payload = {"trades": trades_response.data}
        
        # 3. PROXY Call to AI Microservice
        async with httpx.AsyncClient(timeout=30) as client:
            ai_response = await client.post(f"{settings.AI_SERVICE_URL}/ai/analyze-trades", json=ai_request_payload)
            
        ai_response.raise_for_status()
        
        # 4. Return Insights
        return ai_response.json()
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI Service Down or Failed: {e.response.status_code}")
    except Exception as e:
        print("❌ CRITICAL ERROR TRACEBACK in /insights:")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Critical Error: {str(e)}")


@router.post("/generate-title/{chat_id}", response_model=ChatResponse)
async def generate_title(chat_id: str, current_user: dict = Depends(get_current_active_user)):
    """PROXIES title generation to AI microservice and saves result to DB."""
    user_id = current_user["id"]
    try:
        # 1. Verify ownership and get messages locally
        chat_response = supabase_client.service_client.table("chats").select("*").eq("id", chat_id).eq("user_id", user_id).single().execute()
        if not chat_response.data: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

        messages_data = await asyncio.to_thread(get_messages_for_title_sync, chat_id)
        if not messages_data: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No messages to generate title from")

        # 2. Prepare Proxy Payload
        ai_request_payload = {"messages": messages_data}

        # 3. PROXY Call to AI Microservice
        async with httpx.AsyncClient(timeout=10) as client:
            ai_response = await client.post(f"{settings.AI_SERVICE_URL}/ai/generate-title", json=ai_request_payload)
            
        ai_response.raise_for_status()
        title_data = ai_response.json()
        new_title = title_data.get("title")
        
        if not new_title: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI failed to generate title")

        # 4. Save New Title to DB
        updated_chat = supabase_client.service_client.table("chats")\
            .update({"title": new_title}).eq("id", chat_id).execute(returning="representation")

        return updated_chat.data[0]

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI Service Down or Failed: {e.response.status_code}")
    except Exception as e:
        print("❌ CRITICAL ERROR TRACEBACK in /generate-title:")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Critical Error: {str(e)}")