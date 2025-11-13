import asyncio
from fastapi import APIRouter, HTTPException, status, Depends
from app.apis.models import (
    AIMessageRequest, AIMessageResponse, 
    TradeExtractionRequest, AnalyticsRequest, AnalyticsResponse
)
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client
from app.libs.ai_service import ai_service

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/chat", response_model=AIMessageResponse)
async def ai_chat(
    request: AIMessageRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Send message to AI and get response with optional trade extraction"""
    try:
        # 1. Verify chat ownership (DB Read)
        # FIXED: Use service_client to bypass RLS
        chat_response = supabase_client.service_client.table("chats")\
            .select("*")\
            .eq("id", request.chat_id)\
            .eq("user_id", current_user["id"])\
            .single()\
            .execute()
        
        if not chat_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found or user does not have permission"
            )
        
        # 2. Save User Message (DB Write)
        # FIXED: Use service_client for INSERT
        user_msg = supabase_client.service_client.table("messages").insert({
            "chat_id": request.chat_id,
            "user_id": current_user["id"],
            "content": request.message,
            "role": "user"
        }).execute()
        
        # 3. Get Chat History (DB Read)
        # FIXED: Use service_client for this read
        messages = supabase_client.service_client.table("messages")\
            .select("*")\
            .eq("chat_id", request.chat_id)\
            .order("created_at", desc=False)\
            .execute()

        # 4. CONCURRENT AI CALLS (For Performance)
        
        chat_history_for_ai = [{"role": m["role"], "content": m["content"]} for m in messages.data]
        
        extraction_task = ai_service.extract_trade_from_text(request.message)
        
        generation_task = ai_service.generate_chat_response(
            user_message=request.message,
            chat_history=chat_history_for_ai,
        )
        
        # Run both AI calls concurrently
        extracted_trade, ai_response_text = await asyncio.gather(
            extraction_task, 
            generation_task
        )

        # 5. Save Extracted Trade (DB Write)
        if extracted_trade:
            # FIXED: Use service_client for INSERT
            trade_response = supabase_client.service_client.table("trades").insert({
                "user_id": current_user["id"],
                "ticker": extracted_trade.ticker.upper(),
                "entry_date": extracted_trade.entry_date.isoformat(),
                "entry_price": extracted_trade.entry_price,
                "quantity": extracted_trade.quantity,
                "exit_date": extracted_trade.exit_date.isoformat() if extracted_trade.exit_date else None,
                "exit_price": extracted_trade.exit_price,
                "notes": extracted_trade.notes,
                "profit_loss": (
                    (extracted_trade.exit_price - extracted_trade.entry_price) * extracted_trade.quantity
                    if extracted_trade.exit_price else None
                )
            }).execute()
        
        # 6. Save AI Response (DB Write)
        # FIXED: Use service_client for INSERT
        ai_msg = supabase_client.service_client.table("messages").insert({
            "chat_id": request.chat_id,
            "user_id": current_user["id"],
            "content": ai_response_text,
            "role": "assistant"
        }).execute()
        
        return {
            "message": ai_response_text,
            "trade_extracted": extracted_trade
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in /ai/chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/extract-trade")
async def extract_trade(
    request: TradeExtractionRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Extract trade information from text"""
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
async def get_analytics(
    request: AnalyticsRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Get AI-powered analytics on user's trades"""
    try:
        # Fetch trades with filters
        # FIXED: Use service_client to bypass RLS
        query = supabase_client.service_client.table("trades")\
            .select("*")\
            .eq("user_id", current_user["id"])
        
        if request.start_date:
            query = query.gte("entry_date", request.start_date.isoformat())
        
        if request.end_date:
            query = query.lte("entry_date", end_date.isoformat())
        
        trades_response = query.order("entry_date", desc=True).execute()
        trades = trades_response.data
        
        if not trades:
            return {
                "total_trades": 0,
                "total_profit_loss": 0.0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "best_trade": None,
                "worst_trade": None
            }
        
        # Calculate metrics
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
        
        return {
            "total_trades": total_trades,
            "total_profit_loss": round(total_profit_loss, 2),
            "win_rate": round(win_rate, 2),
            "avg_profit": round(avg_profit, 2),
            "avg_loss": round(avg_loss, 2),
            "best_trade": best_trade,
            "worst_trade": worst_trade
        }
    
    except Exception as e:
        print(f"❌ Error in /ai/analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/insights")
async def get_ai_insights(current_user: dict = Depends(get_current_active_user)):
    """Get AI-generated insights from trading history"""
    try:
        # Fetch recent trades
        # FIXED: Use service_client to bypass RLS
        trades_response = supabase_client.service_client.table("trades")\
            .select("*")\
            .eq("user_id", current_user["id"])\
            .order("entry_date", desc=True)\
            .limit(50)\
            .execute()
        
        # Generate AI insights
        insights = await ai_service.analyze_trades(trades_response.data)
        
        return insights
    
    except Exception as e:
        print(f"❌ Error in /ai/insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )