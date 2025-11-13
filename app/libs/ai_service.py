import json
from typing import Optional, Dict, Any
from datetime import datetime
import google.generativeai as genai  # Replaced Anthropic
from app.libs.config import settings
from app.apis.models import TradeCreate


class AIService:
    """AI service for trade extraction and chat completion using Gemini"""

    def __init__(self):
        # Configure the Gemini client
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # We need separate model instances for different system prompts and tasks

        # 1. Model for Trade Extraction (Forced JSON output)
        today = datetime.now().strftime('%Y-%m-%d')
        extraction_system_prompt = f"""You are a trading journal assistant. Extract trade information from user messages.
        
Return a JSON object with these fields (all required except notes):
{{
    "ticker": "STOCK_SYMBOL",
    "entry_date": "YYYY-MM-DD",
    "entry_price": float,
    "quantity": float,
    "exit_date": "YYYY-MM-DD" or null,
    "exit_price": float or null,
    "notes": "any additional notes" or null
}}

Rules:
- If exit info is not mentioned, set exit_date and exit_price to null
- Default quantity to 1 if not specified
- Use today's date ({today}) if entry_date not specified
- Return ONLY valid JSON, no other text
- If no trade info found, return null"""
        
        extraction_config = genai.GenerationConfig(
            response_mime_type="application/json"
        )
        self.extraction_model = genai.GenerativeModel(
            model_name='models/gemini-2.5-flash',
            system_instruction=extraction_system_prompt,
            generation_config=extraction_config
        )

        # 2. Model for General Chat
        chat_system_prompt = """You are an AI trading journal assistant. Help users:
- Log and track their trades
- Analyze trading patterns
- Provide insights on performance
- Answer questions about their trading history

Be concise, helpful, and encouraging. If a trade was extracted, acknowledge it and provide relevant insights."""
        
        self.chat_model = genai.GenerativeModel(
            model_name='models/gemini-2.5-flash',
            system_instruction=chat_system_prompt
        )
        
        # 3. Model for Trade Analysis (Forced JSON output)
        analysis_config = genai.GenerationConfig(
            response_mime_type="application/json"
        )
        self.analysis_model = genai.GenerativeModel(
            model_name='models/gemini-2.5-flash',
            generation_config=analysis_config
            # No system prompt, as the full instruction is in the user message
        )

    async def extract_trade_from_text(self, text: str) -> Optional[TradeCreate]:
        """Extract trade information from natural language text"""
        
        try:
            # Send the user's text directly. The system prompt is already set.
            response = await self.extraction_model.generate_content_async(text)
            
            content = response.text.strip()
            
            # Handle null response
            if content.lower() == "null":
                return None
            
            # Parse JSON response
            trade_data = json.loads(content)
            
            # Validate and convert to TradeCreate model
            if trade_data and "ticker" in trade_data:
                return TradeCreate(**trade_data)
            
            return None
        
        except Exception as e:
            print(f"Error extracting trade: {e}")
            return None

    async def generate_chat_response(
        self, 
        user_message: str, 
        chat_history: list,
        extracted_trade: Optional[TradeCreate] = None
    ) -> str:
        """Generate AI response for chat conversation"""
        
        # Build conversation history for Gemini
        gemini_history = []
        for msg in chat_history[-10:]:  # Last 10 messages for context
            role = "model" if msg.get("role") == "assistant" else "user"
            gemini_history.append({
                "role": role,
                "parts": [msg.get("content", "")]
            })
        
        # Prepare the new user message
        current_user_content = user_message
        
        # Add trade extraction context if available
        if extracted_trade:
            trade_summary = f"\n\n[Trade extracted: {extracted_trade.ticker} - Entry: ${extracted_trade.entry_price}, Qty: {extracted_trade.quantity}"
            if extracted_trade.exit_price:
                profit_loss = (extracted_trade.exit_price - extracted_trade.entry_price) * extracted_trade.quantity
                trade_summary += f", Exit: ${extracted_trade.exit_price}, P/L: ${profit_loss:.2f}"
            trade_summary += "]"
            current_user_content += trade_summary
            
        try:
            # Start a chat session with the existing history
            chat_session = self.chat_model.start_chat(history=gemini_history)
            
            # Send the new user message (with trade context)
            response = await chat_session.send_message_async(current_user_content)
            
            return response.text
        
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again."

    async def analyze_trades(self, trades: list) -> Dict[str, Any]:
        """Generate AI insights from trade history"""
        
        if not trades:
            return {
                "summary": "No trades to analyze yet.",
                "insights": []
            }
        
        # Prepare trade data for analysis
        trade_summary = []
        for trade in trades[:50]:  # Analyze recent 50 trades
            trade_info = {
                "ticker": trade.get("ticker"),
                "entry_price": trade.get("entry_price"),
                "exit_price": trade.get("exit_price"),
                "profit_loss": trade.get("profit_loss"),
                "date": trade.get("entry_date")
            }
            trade_summary.append(trade_info)
        
        prompt = f"""Analyze these recent trades and provide insights:

{json.dumps(trade_summary, indent=2)}

Provide:
1. Overall performance summary
2. Top 3 patterns or insights
3. Recommendations for improvement

Return as JSON:
{{
    "summary": "brief overview",
    "insights": ["insight 1", "insight 2", "insight 3"]
}}"""

        try:
            # Use the dedicated analysis model for JSON output
            response = await self.analysis_model.generate_content_async(prompt)
            
            content = response.text.strip()
            analysis = json.loads(content)
            
            return analysis
        
        except Exception as e:
            print(f"Error analyzing trades: {e}")
            return {
                "summary": "Analysis unavailable",
                "insights": []
            }


# Global AI service instance
ai_service = AIService()