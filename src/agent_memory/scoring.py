"""Importance + recency scoring and decay/pruning policy.

Recency uses exponential decay with a configurable half-life (default 30
days): a record's recency score halves every half-life. The combined score
weights stated importance above recency, so a high-importance old record can
outrank a trivial recent one.
"""
from __future__ import annotations

from datetime import datetime, timezone


def age_seconds(created_at: datetime, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - created_at).total_seconds())


def recency_score(created_at: datetime, now: datetime | None = None,
                  half_life_days: float = 30.0) -> float:
    """In (0, 1]: 1.0 at creation, 0.5 after one half-life, decaying after."""
    half_life_seconds = half_life_days * 86400.0
    return 0.5 ** (age_seconds(created_at, now) / half_life_seconds)


def combined_score(importance: float, created_at: datetime,
                   now: datetime | None = None,
                   importance_weight: float = 0.6) -> float:
    if not 0.0 <= importance <= 1.0:
        raise ValueError("importance must be in [0, 1]")
    recency = recency_score(created_at, now)
    return importance_weight * importance + (1.0 - importance_weight) * recency


def is_prunable(importance: float, created_at: datetime,
                now: datetime | None = None, retention_days: float = 90.0,
                min_importance: float = 0.3) -> bool:
    """Prune only stale AND low-importance records; important history survives."""
    return (age_seconds(created_at, now) > retention_days * 86400.0
            and importance < min_importance)
