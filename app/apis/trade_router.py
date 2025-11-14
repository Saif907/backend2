from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import date
from app.apis.models import TradeCreate, TradeUpdate, TradeResponse
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client
import asyncio # ADDED for concurrency

router = APIRouter(prefix="/trades", tags=["Trades"])

# --- Helper Functions (Synchronous Wrappers for Blocking DB Calls) ---

def calculate_profit_loss(entry_price, exit_price, quantity):
    """Calculates P&L. Assumes prices/quantity are already converted to float/numeric types."""
    if exit_price is not None:
        return (exit_price - entry_price) * quantity
    return None

def create_trade_sync(trade_data: TradeCreate, user_id: str):
    """Blocking function to create a new trade."""
    profit_loss = calculate_profit_loss(
        trade_data.entry_price, trade_data.exit_price, trade_data.quantity
    )
    
    response = supabase_client.service_client.table("trades").insert({
        "user_id": user_id,
        "ticker": trade_data.ticker.upper(),
        "entry_date": trade_data.entry_date.isoformat(),
        "entry_price": trade_data.entry_price,
        "quantity": trade_data.quantity,
        "exit_date": trade_data.exit_date.isoformat() if trade_data.exit_date else None,
        "exit_price": trade_data.exit_price,
        "notes": trade_data.notes,
        "profit_loss": profit_loss
    }).execute()
    
    if not response.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create trade")
    
    return response.data[0]


def get_trades_sync(user_id: str, ticker: Optional[str], start_date: Optional[date], end_date: Optional[date]):
    """Blocking function to get filtered trades."""
    query = supabase_client.service_client.table("trades")\
        .select("*")\
        .eq("user_id", user_id)
    
    if ticker:
        query = query.eq("ticker", ticker.upper())
    
    if start_date:
        query = query.gte("entry_date", start_date.isoformat())
    
    if end_date:
        query = query.lte("entry_date", end_date.isoformat())
    
    response = query.order("entry_date", desc=True).execute()
    return response.data


def get_trade_sync(trade_id: str, user_id: str):
    """Blocking function to get a specific trade and verify ownership."""
    response = supabase_client.service_client.table("trades")\
        .select("*")\
        .eq("id", trade_id)\
        .eq("user_id", user_id)\
        .single()\
        .execute()
    
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    
    return response.data


def update_trade_sync(trade_id: str, trade_data: TradeUpdate, user_id: str):
    """Blocking function to update an existing trade."""
    # 1. Verify ownership and get existing data
    existing = get_trade_sync(trade_id, user_id)
    
    # 2. Prepare update data
    update_data = {k: v for k, v in trade_data.dict(exclude_unset=True).items()}
    
    # 3. Recalculate profit/loss if prices or quantity are updated
    entry_price = update_data.get("entry_price", existing["entry_price"])
    exit_price = update_data.get("exit_price", existing["exit_price"])
    quantity = update_data.get("quantity", existing["quantity"])
        
    update_data["profit_loss"] = calculate_profit_loss(entry_price, exit_price, quantity)
    
    # 4. Convert dates to ISO format
    if "entry_date" in update_data:
        update_data["entry_date"] = update_data["entry_date"].isoformat()
    if "exit_date" in update_data and update_data["exit_date"] is not None:
        update_data["exit_date"] = update_data["exit_date"].isoformat()
    # Handle explicit removal of exit_date/price if sent as None
    elif "exit_date" in update_data and update_data["exit_date"] is None:
        update_data["exit_price"] = None

    # 5. Perform the update
    response = supabase_client.service_client.table("trades")\
        .update(update_data)\
        .eq("id", trade_id)\
        .execute()
    
    return response.data[0]


def delete_trade_sync(trade_id: str, user_id: str):
    """Blocking function to delete a trade."""
    # Verify ownership (will raise 404 if not found or not owned)
    get_trade_sync(trade_id, user_id) 
    
    # Perform delete
    supabase_client.service_client.table("trades")\
        .delete()\
        .eq("id", trade_id)\
        .execute()

# --- Router Endpoints (Non-Blocking) ---

@router.post("", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def create_trade(
    trade_data: TradeCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new trade (Now non-blocking)"""
    try:
        # Use asyncio.to_thread to run the synchronous DB call in a thread
        return await asyncio.to_thread(create_trade_sync, trade_data, current_user["id"])
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating trade: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=List[TradeResponse])
async def get_trades(
    current_user: dict = Depends(get_current_active_user),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date")
):
    """Get all trades for current user with optional filters (Now non-blocking)"""
    try:
        # Use asyncio.to_thread to run the synchronous DB call in a thread
        return await asyncio.to_thread(
            get_trades_sync, 
            current_user["id"], 
            ticker, 
            start_date, 
            end_date
        )
    
    except Exception as e:
        print(f"❌ Error getting trades: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get a specific trade (Now non-blocking)"""
    try:
        # Use asyncio.to_thread to run the synchronous DB call in a thread
        return await asyncio.to_thread(get_trade_sync, trade_id, current_user["id"])
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting trade: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{trade_id}", response_model=TradeResponse)
async def update_trade(
    trade_id: str,
    trade_data: TradeUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update an existing trade (Now non-blocking)"""
    try:
        # Use asyncio.to_thread to run the synchronous DB call in a thread
        return await asyncio.to_thread(update_trade_sync, trade_id, trade_data, current_user["id"])
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating trade: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Delete a trade (Now non-blocking)"""
    try:
        # Use asyncio.to_thread to run the synchronous DB call in a thread
        await asyncio.to_thread(delete_trade_sync, trade_id, current_user["id"])
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting trade: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )