"""Tests for Delivery module."""

import pytest
from unittest.mock import AsyncMock, patch
from telegram.error import TelegramError

from app.intervene.delivery import TelegramNotifier, generate_inoculation_card

@pytest.mark.asyncio
async def test_telegram_notifier_success():
    notifier = TelegramNotifier("fake_token", "fake_chat_id")
    assert notifier.available()
    
    with patch('app.intervene.delivery.Bot') as mock_bot_class:
        # mock_bot_class.return_value is the Bot instance
        # Since it's used as an async context manager: `async with Bot() as bot:`
        # we need its __aenter__ to return our mock bot
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value.__aenter__.return_value = mock_bot_instance
        
        result = await notifier.send({"verdict": "FALSE", "summary": "Test summary"})
        
        assert result == 1
        mock_bot_instance.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_telegram_notifier_failure():
    notifier = TelegramNotifier("fake_token", "fake_chat_id")
    
    with patch('app.intervene.delivery.Bot') as mock_bot_class:
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message.side_effect = TelegramError("Network error")
        mock_bot_class.return_value.__aenter__.return_value = mock_bot_instance
        
        result = await notifier.send({"verdict": "FALSE", "summary": "Test summary"})
        
        # Must not raise
        assert result == 0

def test_generate_inoculation_card():
    card = generate_inoculation_card("FALSE", "Fake news", "2026-07-30")
    assert "FACT CHECK: FALSE" in card
    assert "#dc2626" in card
    assert "Fake news" in card
