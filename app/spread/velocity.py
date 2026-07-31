"""Velocity heuristics for viral spread detection."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from app.config import get_thresholds


def calculate_velocity(report_timestamps: Sequence[datetime], now: datetime | None = None) -> str:
    """Detect viral spread based on report density over time.
    
    Uses config/thresholds.yaml for the time windows and counts.
    Returns 'high', 'medium', or 'low'.
    """
    if now is None:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
    th = get_thresholds()
    high_count = th.i("spread.velocity.high_count")
    high_minutes = th.i("spread.velocity.high_minutes")
    medium_count = th.i("spread.velocity.medium_count")
    medium_minutes = th.i("spread.velocity.medium_minutes")
    
    high_cutoff = now - timedelta(minutes=high_minutes)
    recent_high = sum(1 for t in report_timestamps if t >= high_cutoff)
    
    if recent_high >= high_count:
        return "high"
        
    medium_cutoff = now - timedelta(minutes=medium_minutes)
    recent_medium = sum(1 for t in report_timestamps if t >= medium_cutoff)
    
    if recent_medium >= medium_count:
        return "medium"
        
    return "low"
