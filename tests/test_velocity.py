"""Tests for velocity heuristics."""

from datetime import datetime, timedelta, timezone

from app.spread.velocity import calculate_velocity


def test_calculate_velocity():
    now = datetime.now(timezone.utc)
    
    # Low: 1 report
    assert calculate_velocity([now], now) == "low"
    
    # Medium: 3 reports in 30 minutes
    assert calculate_velocity([now, now - timedelta(minutes=5), now - timedelta(minutes=9)], now) == "medium"
    
    # High: 5 reports in 10 minutes
    assert calculate_velocity([
        now, 
        now - timedelta(minutes=2),
        now - timedelta(minutes=4),
        now - timedelta(minutes=6),
        now - timedelta(minutes=8),
    ], now) == "high"
    
    # High cutoff check: 5 reports but 1 is 11 minutes ago -> medium
    assert calculate_velocity([
        now, 
        now - timedelta(minutes=2),
        now - timedelta(minutes=4),
        now - timedelta(minutes=6),
        now - timedelta(minutes=11),
    ], now) == "medium"

    # Medium cutoff check: 3 reports but 1 is 31 minutes ago -> low
    assert calculate_velocity([
        now, 
        now - timedelta(minutes=2),
        now - timedelta(minutes=31),
    ], now) == "low"
