import asyncio
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.apis.models import UserDataInternal, OverviewMetrics # IMPORTED: Pydantic models
from app.auth.utils import get_current_active_user
from app.libs.supabase_client import supabase_client
from datetime import datetime, timedelta

router = APIRouter(prefix="/internal", tags=["Internal Console"])

# --- Internal Console Data Models (for Mocking) ---
# NOTE: These objects are defined here to simplify the mock return types,
# but they represent the structures the frontend expects.

class InternalChatSession(object):
    """Data structure for /internal/sessions mock endpoint."""
    def __init__(self, id, title, created_at, user_id, user_email, message_count):
        self.id = id
        self.title = title
        self.created_at = created_at
        self.user_id = user_id
        self.user_email = user_email
        self.message_count = message_count

class InternalTradeAnalytics(object):
    """Data structure for /internal/analytics mock endpoint."""
    def __init__(self, totalTrades, avgProfit, winRate, avgHoldTime):
        self.totalTrades = totalTrades
        self.avgProfit = avgProfit
        self.winRate = winRate
        self.avgHoldTime = avgHoldTime
        
class InternalBillingMetrics(object):
    """Data structure for /internal/billing mock endpoint."""
    def __init__(self, monthlyRevenue, paidUsers, avgRevenuePerUser, churnRate):
        self.monthlyRevenue = monthlyRevenue
        self.paidUsers = paidUsers
        self.avgRevenuePerUser = avgRevenuePerUser
        self.churnRate = churnRate


# --- Router Endpoints ---

@router.get("/users", response_model=List[UserDataInternal])
async def get_all_users_and_metrics(current_user: dict = Depends(get_current_active_user)):
    """
    Retrieves all user profiles along with their chat and trade counts in one optimized request.
    Requires founder role (enforced by the underlying database RPC function).
    """
    
    # 1. Fetch anonymized metrics using the efficient, role-protected database function (RPC)
    try:
        # RPC calls are blocking, so we run it safely in a thread (Efficiency)
        analytics_result = await asyncio.to_thread(
            supabase_client.service_client.rpc('get_anonymized_user_analytics', {}).execute
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch analytics from DB RPC: {str(e)}")

    # Check for the database-side access denial error (Protection)
    if analytics_result.error and analytics_result.error['message'] == 'Access denied':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Requires founder role.")
    
    # 2. Get basic profiles for consent status 
    try:
        profiles_response = await asyncio.to_thread(
             supabase_client.service_client.table("profiles")
            .select("id, pseudonymous_id, consent_given, created_at, updated_at")
            .order("created_at", desc=True)
            .execute
        )
        
        profiles = profiles_response.data or []
        profiles_map = {p['pseudonymous_id']: p for p in profiles if p.get('pseudonymous_id')}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch profile metadata: {str(e)}")

    # 3. Combine the data and map it to the frontend model
    final_data = []
    
    for row in analytics_result.data:
        pseudo_id = row.get('pseudonymous_id')
        profile_data = profiles_map.get(pseudo_id, {})
        
        join_date_str = row.get('join_date') or profile_data.get('created_at')
        created_at_dt = datetime.fromisoformat(join_date_str) if join_date_str else datetime.now()

        final_data.append(UserDataInternal(
            id=profile_data.get("id", "N/A"),
            pseudonymous_id=pseudo_id,
            consent_given=profile_data.get("consent_given", False),
            created_at=created_at_dt,
            updated_at=profile_data.get("updated_at", created_at_dt),
            trades_count=row.get('trade_count', 0),
            chats_count=row.get('chat_count', 0),
        ))

    return final_data


@router.get("/sessions")
async def get_all_chat_sessions(current_user: dict = Depends(get_current_active_user)):
    """
    MOCK: Retrieves all chat sessions and their metrics. 
    (Placeholder until a single efficient RPC is written for this.)
    """
    await asyncio.sleep(0.1) 

    mock_sessions = [
        InternalChatSession(
            id=f"chat_{i}",
            title=f"Trade Review: Session {i}",
            created_at=(datetime.now() - timedelta(days=i)).isoformat(),
            user_id="user_id_mock",
            user_email=f"user{i}@mock.com",
            message_count=10 - i // 2,
        ) for i in range(10)
    ]

    return mock_sessions


@router.get("/metrics", response_model=OverviewMetrics) 
async def get_overview_metrics(current_user: dict = Depends(get_current_active_user)):
    """
    MOCK: Retrieves key platform metrics for the founder overview dashboard.
    """
    await asyncio.sleep(0.05) 

    # MOCK DATA RETURNED: Structure matches the OverviewMetrics model
    return OverviewMetrics(
        totalUsers=210, 
        activeUsersWeek=45,
        totalTrades=1024, 
        totalChats=350,
    )


@router.get("/analytics") # NEW ENDPOINT
async def get_trade_analytics(current_user: dict = Depends(get_current_active_user)):
    """
    MOCK: Retrieves aggregate trading behavior across all users.
    """
    await asyncio.sleep(0.05) 

    return InternalTradeAnalytics(
        totalTrades=1024,
        avgProfit=1330.45,
        winRate=64.3,
        avgHoldTime=2.4
    )


@router.get("/billing") # NEW ENDPOINT
async def get_billing_metrics(current_user: dict = Depends(get_current_active_user)):
    """
    MOCK: Retrieves revenue and subscription analytics.
    """
    await asyncio.sleep(0.05) 

    return InternalBillingMetrics(
        monthlyRevenue=42580,
        paidUsers=32,
        avgRevenuePerUser=1330,
        churnRate=4.2
    )