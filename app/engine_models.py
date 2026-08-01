"""Unified, provider-neutral records used by the decision engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


Outcome = Literal["1", "X", "2"]


@dataclass(frozen=True)
class SourcePolicy:
    key: str
    label_he: str
    reliability: float
    automated_access: bool
    terms_url: str
    notes_he: str = ""


@dataclass
class UnifiedMatch:
    external_id: str
    competition: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    status: str = "scheduled"
    home_score: int | None = None
    away_score: int | None = None
    home_odds: float | None = None
    draw_odds: float | None = None
    away_odds: float | None = None
    source: str = "manual"
    observed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamSnapshot:
    team: str
    played: int = 0
    points: int = 0
    goals_for: int = 0
    goals_against: int = 0
    home_played: int = 0
    home_points: int = 0
    away_played: int = 0
    away_points: int = 0
    recent_points: list[int] = field(default_factory=list)
    cards: int | None = None
    suspensions: int | None = None

