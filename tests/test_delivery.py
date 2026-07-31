"""Tests for Delivery module."""

import pytest
from unittest.mock import AsyncMock, patch
from telegram.error import TelegramError

from app.intervene.delivery import TelegramNotifier, generate_inoculation_card

@pytest.mark.asyncio
async def test_telegram_notifier_success():
    notifier = TelegramNotifier("fake_token", "fake_chat_id")
    assert notifier.available()
    
    with patch.object(notifier, 'bot') as mock_bot:
        mock_bot.send_message = AsyncMock()
        
        result = await notifier.send({"verdict": "FALSE", "summary": "Test summary"})
        
        assert result == 1
        mock_bot.send_message.assert_called_once_with(
            chat_id="fake_chat_id", 
            text="🚨 ALERT: FALSE\n\nTest summary"
        )

@pytest.mark.asyncio
async def test_telegram_notifier_failure():
    notifier = TelegramNotifier("fake_token", "fake_chat_id")
    
    with patch.object(notifier, 'bot') as mock_bot:
        mock_bot.send_message = AsyncMock(side_effect=TelegramError("Network error"))
        
        result = await notifier.send({"verdict": "FALSE", "summary": "Test summary"})
        
        # Must not raise
        assert result == 0

def test_generate_inoculation_card():
    card = generate_inoculation_card("FALSE", "Fake news", "2026-07-30")
    assert "FACT CHECK: FALSE" in card
    assert "#dc2626" in card
    assert "Fake news" in card
