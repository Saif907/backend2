from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date


# ============ Auth Models ============
class UserSignUp(BaseModel):
    """User registration data"""
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserSignIn(BaseModel):
    """User login credentials"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT access token response"""
    access_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None


class TokenData(BaseModel):
    """Data stored in JWT token"""
    user_id: str
    email: Optional[str] = None


class UserProfile(BaseModel):
    """
    User profile data (Updated to reflect post-PII removal DB schema)
    """
    id: str
    created_at: datetime
    updated_at: datetime
    # Removed PII fields: email, full_name, avatar_url
    
    # Added privacy fields from the latest migration
    consent_date: Optional[datetime] = None
    consent_given: Optional[bool] = None
    privacy_version: Optional[int] = None
    pseudonymous_id: Optional[str] = None


class UserResponse(BaseModel):
    """User response with profile data"""
    user: UserProfile
    session: Optional[dict] = None


# ============ Chat Models ============
class ChatCreate(BaseModel):
    """Create new chat session"""
    title: str


class ChatResponse(BaseModel):
    """Chat session response"""
    id: str
    title: str
    user_id: str
    created_at: datetime
    updated_at: datetime


# ============ Message Models ============
class MessageCreate(BaseModel):
    """Create new message"""
    chat_id: str
    content: str
    role: str  # 'user' or 'assistant'


class MessageResponse(BaseModel):
    """Message response"""
    id: str
    chat_id: str
    user_id: str
    content: str
    role: str
    created_at: datetime


class ChatWithMessages(BaseModel):
    """Chat with all messages"""
    chat: ChatResponse
    messages: List[MessageResponse]


# ============ Trade Models ============
class TradeCreate(BaseModel):
    """Create new trade (Removed profit_loss)"""
    ticker: str
    entry_date: date
    entry_price: float
    quantity: float
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    notes: Optional[str] = None
    # Removed: profit_loss: Optional[float] = None


class TradeUpdate(BaseModel):
    """Update existing trade"""
    ticker: Optional[str] = None
    entry_date: Optional[date] = None
    entry_price: Optional[float] = None
    quantity: Optional[float] = None
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    notes: Optional[str] = None
    # Removed: profit_loss: Optional[float] = None


class TradeResponse(BaseModel):
    """Trade response"""
    id: str
    user_id: str
    ticker: str
    entry_date: date
    entry_price: float
    quantity: float
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    notes: Optional[str] = None
    profit_loss: Optional[float] = None
    created_at: datetime
    updated_at: datetime


# ============ AI Models ============
class AIMessageRequest(BaseModel):
    """Request for AI chat completion"""
    chat_id: str
    message: str


class AIMessageResponse(BaseModel):
    """AI response"""
    message: str
    trade_extracted: Optional[TradeCreate] = None


class TradeExtractionRequest(BaseModel):
    """Request to extract trade from text"""
    text: str


class AnalyticsRequest(BaseModel):
    """Request for trade analytics"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class AnalyticsResponse(BaseModel):
    """Response with trade analytics summary"""
    total_trades: int
    total_profit_loss: float
    win_rate: float
    avg_profit: float
    avg_loss: float
    best_trade: Optional[dict] = None
    worst_trade: Optional[dict] = None


class Insight(BaseModel):
    """Single AI-generated insight"""
    title: str
    description: str
    type: str # success, warning, info

class InsightsResponse(BaseModel):
    """List of AI insights"""
    insights: List[Insight]