import asyncio
from fastapi import APIRouter, HTTPException, status, Depends
from app.apis.models import (
    AIMessageRequest, AIMessageResponse, 
    TradeExtractionRequest, AnalyticsRequest, AnalyticsResponse,
    ChatResponse # ADDED
)
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client
from app.libs.ai_service import ai_service
import json

router = APIRouter(prefix="/ai", tags=["AI"])

# --- Helper Functions (Synchronous Wrappers for Blocking DB Calls) ---
# We use these so they can be safely run concurrently via asyncio.to_thread

def get_chat_and_trades_sync(chat_id, user_id):
    """Performs the blocking DB reads for chat context."""
    # Get Chat History (Sync DB Read)
    messages_response = supabase_client.service_client.table("messages")\
        .select("*")\
        .eq("chat_id", chat_id)\
        .order("created_at", desc=False)\
        .execute()

    # FETCH TRADE HISTORY (Sync DB Read)
    trade_history_response = supabase_client.service_client.table("trades")\
        .select("ticker, entry_price, exit_price, quantity, entry_date, profit_loss, notes")\
        .eq("user_id", user_id)\
        .order("entry_date", desc=True)\
        .limit(20) \
        .execute()
    
    return messages_response.data, trade_history_response.data

def insert_user_message_sync(chat_id, user_id, content):
    """Performs the blocking DB write for user message."""
    return supabase_client.service_client.table("messages").insert({
        "chat_id": chat_id,
        "user_id": user_id,
        "content": content,
        "role": "user"
    }).execute()

def insert_ai_message_sync(chat_id, user_id, content):
    """Performs the blocking DB write for AI message."""
    return supabase_client.service_client.table("messages").insert({
        "chat_id": chat_id,
        "user_id": user_id,
        "content": content,
        "role": "assistant"
    }).execute()
    
def insert_trade_sync(user_id, extracted_trade, profit_loss):
    """Performs the blocking DB write for a new trade."""
    return supabase_client.service_client.table("trades").insert({
        "user_id": user_id,
        "ticker": extracted_trade.ticker.upper(),
        "entry_date": extracted_trade.entry_date.isoformat(),
        "entry_price": extracted_trade.entry_price,
        "quantity": extracted_trade.quantity, 
        "exit_date": extracted_trade.exit_date.isoformat() if extracted_trade.exit_date else None,
        "exit_price": extracted_trade.exit_price,
        "notes": extracted_trade.notes,
        "profit_loss": profit_loss
    }).execute()

# --- Router Function (Optimized for Concurrency) ---

@router.post("/chat", response_model=AIMessageResponse)
async def ai_chat(
    request: AIMessageRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Send message to AI and get response with optional trade extraction"""
    user_id = current_user["id"]
    chat_id = request.chat_id
    
    try:
        # 1. Verify chat ownership (Blocking DB Read - Kept sequential to fail fast)
        chat_response = supabase_client.service_client.table("chats")\
            .select("*")\
            .eq("id", chat_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not chat_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found or user does not have permission"
            )
        
        # 2. Concurrently execute initial I/O tasks (Speed/Smoothness)
        # We use asyncio.to_thread for synchronous DB calls to prevent blocking the event loop.
        user_msg_task = asyncio.to_thread(insert_user_message_sync, chat_id, user_id, request.message)
        db_read_task = asyncio.to_thread(get_chat_and_trades_sync, chat_id, user_id)
        extraction_task = ai_service.extract_trade_from_text(request.message) # Non-blocking AI call

        try:
            (user_msg_response, (messages_data, trade_history), extracted_trade) = await asyncio.gather(
                user_msg_task, 
                db_read_task,
                extraction_task
            )
        except Exception as e:
            print(f"❌ Error during initial concurrent tasks: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="A critical initial task failed (DB or AI Extraction). " + str(e)
            )

        # 3. Generate AI Response (Non-Blocking LLM Call)
        chat_history_for_ai = [{"role": m["role"], "content": m["content"]} for m in messages_data]
        ai_response_text = "I apologize, but I'm having trouble processing your request right now. Please try again."
        
        try:
            ai_response_text = await ai_service.generate_chat_response(
                user_message=request.message,
                chat_history=chat_history_for_ai,
                trade_history=trade_history
            )
        except Exception as e:
            # Protection: If the main AI chat generation fails, we still proceed with a fallback message
            print(f"❌ Error during main AI generation: {e}")
            # The fallback message is already set above
        
        # 4. Concurrently save final data (Protection/Stability)
        
        trade_insert_task = None
        profit_loss_value = None
        if extracted_trade:
            # Calculate profit/loss before saving (Same logic as original code)
            profit_loss_value = None
            if extracted_trade.exit_price:
                quantity = float(extracted_trade.quantity)
                profit_loss_value = (extracted_trade.exit_price - extracted_trade.entry_price) * quantity

            # Task D: Save Extracted Trade (Blocking DB Write, now in a thread)
            trade_insert_task = asyncio.to_thread(insert_trade_sync, user_id, extracted_trade, profit_loss_value)
        
        # Task E: Save AI Response (Blocking DB Write, now in a thread)
        ai_msg_task = asyncio.to_thread(insert_ai_message_sync, chat_id, user_id, ai_response_text)
        
        final_tasks = [ai_msg_task]
        if trade_insert_task:
            final_tasks.append(trade_insert_task)
            
        # Wait for all final writes before returning to the user
        await asyncio.gather(*final_tasks)
        
        # 5. Final response
        return {
            "message": ai_response_text,
            "trade_extracted": extracted_trade
        }
    
    except HTTPException:
        # Pass FastAPI exceptions directly
        raise
    except Exception as e:
        # Catches unexpected critical failures (e.g., connection lost)
        print(f"❌ Critical error in /ai/chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected critical error occurred: {str(e)}"
        )


@router.post("/extract-trade")
# ... (This endpoint remains unchanged)
async def extract_trade(
    request: TradeExtractionRequest,
    current_user: dict = Depends(get_current_active_user)
):
    try:
        extracted_trade = await ai_service.extract_trade_from_text(request.text)
        
        if not extracted_trade:
            return {
                "trade": None,
                "message": "No trade information found in the text"
            }
        
        return {
            "trade": extracted_trade,
            "message": "Trade information extracted successfully"
        }
    
    except Exception as e:
        print(f"❌ Error in /ai/extract-trade: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/analytics", response_model=AnalyticsResponse)
# ... (This endpoint remains unchanged)
async def get_analytics(
    request: AnalyticsRequest,
    current_user: dict = Depends(get_current_active_user)
):
    try:
        query = supabase_client.service_client.table("trades")\
            .select("*")\
            .eq("user_id", current_user["id"])
        
        if request.start_date:
            query = query.gte("entry_date", request.start_date.isoformat())
        
        if request.end_date:
            query = query.lte("entry_date", request.end_date.isoformat())
        
        trades_response = query.order("entry_date", desc=True).execute()
        trades = trades_response.data
        
        if not trades:
            return { "total_trades": 0, "total_profit_loss": 0.0, "win_rate": 0.0, "avg_profit": 0.0, "avg_loss": 0.0, "best_trade": None, "worst_trade": None }
        
        closed_trades = [t for t in trades if t.get("profit_loss") is not None]
        total_trades = len(closed_trades)
        total_profit_loss = sum(t.get("profit_loss", 0) for t in closed_trades)
        winning_trades = [t for t in closed_trades if t.get("profit_loss", 0) > 0]
        losing_trades = [t for t in closed_trades if t.get("profit_loss", 0) < 0]
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        avg_profit = (sum(t["profit_loss"] for t in winning_trades) / len(winning_trades)) if winning_trades else 0
        avg_loss = (sum(t["profit_loss"] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
        best_trade = max(closed_trades, key=lambda t: t.get("profit_loss", 0)) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda t: t.get("profit_loss", 0)) if closed_trades else None
        
        return { "total_trades": total_trades, "total_profit_loss": round(total_profit_loss, 2), "win_rate": round(win_rate, 2), "avg_profit": round(avg_profit, 2), "avg_loss": round(avg_loss, 2), "best_trade": best_trade, "worst_trade": worst_trade }
    
    except Exception as e:
        print(f"❌ Error in /ai/analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/insights")
# ... (This endpoint remains unchanged)
async def get_ai_insights(current_user: dict = Depends(get_current_active_user)):
    try:
        trades_response = supabase_client.service_client.table("trades")\
            .select("*")\
            .eq("user_id", current_user["id"])\
            .order("entry_date", desc=True)\
            .limit(50)\
            .execute()
        
        insights = await ai_service.analyze_trades(trades_response.data)
        
        return insights
    
    except Exception as e:
        print(f"❌ Error in /ai/insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# NEW ENDPOINT FOR AUTO-TITLING
@router.post("/generate-title/{chat_id}", response_model=ChatResponse)
async def generate_title(
    chat_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Generate and save an AI-powered title for a chat"""
    try:
        # 1. Verify chat ownership
        chat_response = supabase_client.service_client.table("chats")\
            .select("*")\
            .eq("id", chat_id)\
            .eq("user_id", current_user["id"])\
            .single()\
            .execute()
        
        if not chat_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found or user does not have permission"
            )

        # 2. Get first 4 messages for context
        messages = supabase_client.service_client.table("messages")\
            .select("role, content")\
            .eq("chat_id", chat_id)\
            .order("created_at", desc=False)\
            .limit(4)\
            .execute()
            
        if not messages.data or len(messages.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No messages in chat to generate title from"
            )

        # 3. Ask AI to generate a title
        new_title = await ai_service.generate_title_for_chat(messages.data)
        
        if not new_title:
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI failed to generate title"
            )

        # 4. Save the new title to the chat
        updated_chat = supabase_client.service_client.table("chats")\
            .update({"title": new_title})\
            .eq("id", chat_id)\
            .execute(returning="representation")

        return updated_chat.data[0]

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in /ai/generate-title: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )