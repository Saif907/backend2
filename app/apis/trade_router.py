from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import date
from app.apis.models import TradeCreate, TradeUpdate, TradeResponse
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client

router = APIRouter(prefix="/trades", tags=["Trades"])


@router.post("", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def create_trade(
    trade_data: TradeCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new trade"""
    try:
        # Calculate profit/loss if exit data exists
        profit_loss = None
        if trade_data.exit_price is not None:
            profit_loss = (trade_data.exit_price - trade_data.entry_price) * trade_data.quantity
        
        # FIXED: Use service_client for INSERT operation
        response = supabase_client.service_client.table("trades").insert({
            "user_id": current_user["id"],
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create trade"
            )
        
        return response.data[0]
    
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
    """Get all trades for current user with optional filters"""
    try:
        # FIXED: Use service_client for this protected SELECT operation
        query = supabase_client.service_client.table("trades")\
            .select("*")\
            .eq("user_id", current_user["id"])
        
        if ticker:
            query = query.eq("ticker", ticker.upper())
        
        if start_date:
            query = query.gte("entry_date", start_date.isoformat())
        
        if end_date:
            query = query.lte("entry_date", end_date.isoformat())
        
        response = query.order("entry_date", desc=True).execute()
        
        return response.data
    
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
    """Get a specific trade"""
    try:
        # FIXED: Use service_client for this protected SELECT operation
        response = supabase_client.service_client.table("trades")\
            .select("*")\
            .eq("id", trade_id)\
            .eq("user_id", current_user["id"])\
            .single()\
            .execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trade not found"
            )
        
        return response.data
    
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
    """Update an existing trade"""
    try:
        # Verify ownership
        # FIXED: Use service_client for the verification read
        existing = supabase_client.service_client.table("trades")\
            .select("*")\
            .eq("id", trade_id)\
            .eq("user_id", current_user["id"])\
            .single()\
            .execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trade not found"
            )
        
        # Prepare update data
        update_data = {k: v for k, v in trade_data.dict(exclude_unset=True).items()}
        
        # Recalculate profit/loss if exit price updated
        if "exit_price" in update_data or "entry_price" in update_data or "quantity" in update_data:
            entry_price = update_data.get("entry_price", existing.data["entry_price"])
            exit_price = update_data.get("exit_price", existing.data["exit_price"])
            quantity = update_data.get("quantity", existing.data["quantity"])
            
            if exit_price is not None:
                update_data["profit_loss"] = (exit_price - entry_price) * quantity
            elif exit_price is None:
                 update_data["profit_loss"] = None
        
        # Convert dates to ISO format
        if "entry_date" in update_data:
            update_data["entry_date"] = update_data["entry_date"].isoformat()
        if "exit_date" in update_data and update_data["exit_date"] is not None:
            update_data["exit_date"] = update_data["exit_date"].isoformat()
        
        # FIXED: Use service_client for UPDATE operation
        response = supabase_client.service_client.table("trades")\
            .update(update_data)\
            .eq("id", trade_id)\
            .execute()
        
        return response.data[0]
    
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
    """Delete a trade"""
    try:
        # Verify ownership
        # FIXED: Use service_client for the verification read
        existing = supabase_client.service_client.table("trades")\
            .select("*")\
            .eq("id", trade_id)\
            .eq("user_id", current_user["id"])\
            .single()\
            .execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trade not found"
            )
        
        # FIXED: Use service_client for DELETE operation
        supabase_client.service_client.table("trades")\
            .delete()\
            .eq("id", trade_id)\
            .execute()
        
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting trade: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )