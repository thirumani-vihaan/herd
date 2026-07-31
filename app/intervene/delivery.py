"""Delivery and Alerting."""
from __future__ import annotations

import logging
from typing import Any

from telegram import Bot
from telegram.error import TelegramError

from app.interfaces import Notifier

logger = logging.getLogger(__name__)

class TelegramNotifier(Notifier):
    """Delivers alerts via Telegram."""
    
    channel: str = "telegram"
    
    def __init__(self, token: str | None, admin_chat_id: str | None) -> None:
        self.token = token
        self.admin_chat_id = admin_chat_id
        self.bot = Bot(token) if token else None
        
    def available(self) -> bool:
        return bool(self.token and self.admin_chat_id)
        
    async def send(self, alert: Any) -> int:
        """Send the alert. Returns number of successful deliveries.
        MUST NEVER RAISE.
        """
        if not self.available() or not self.bot:
            return 0
            
        try:
            message = str(alert)
            if isinstance(alert, dict):
                verdict = alert.get('verdict', 'UNKNOWN')
                summary = alert.get('summary', '')
                claim_text = alert.get('claim', {}).get('text', 'No claim text found.')
                
                message = f"🚨 ALERT: {verdict}\n\nCLAIM:\n\"{claim_text}\"\n\nANALYSIS:\n{summary}"
            
            await self.bot.send_message(chat_id=self.admin_chat_id, text=message)
            return 1
        except TelegramError as e:
            logger.error(f"Telegram delivery failed: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in Telegram delivery: {e}")
            return 0


class WebSocketNotifier(Notifier):
    """Delivers alerts via WebSocket."""
    
    channel: str = "websocket"
    
    def __init__(self) -> None:
        pass
        
    def available(self) -> bool:
        return True
        
    async def send(self, alert: Any) -> int:
        logger.info(f"WebSocket send: {alert}")
        return 1


def generate_inoculation_card(verdict: str, summary: str, date: str) -> str:
    """Generate HTML inoculation card."""
    color = "#dc2626" if verdict == "FALSE" else "#ca8a04" if verdict == "MISLEADING" else "#16a34a"
    return f"""
    <div style="border: 2px solid {color}; padding: 16px; border-radius: 8px; font-family: sans-serif;">
        <h2 style="color: {color}; margin-top: 0;">FACT CHECK: {verdict}</h2>
        <p><strong>Date:</strong> {date}</p>
        <p>{summary}</p>
    </div>
    """
