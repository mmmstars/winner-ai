"""Leakage-safe pre-match football features from completed matches only."""

from __future__ import annotations

from app.engine_models import TeamSnapshot


def snapshot_features(team: TeamSnapshot) -> dict[str, float | int | None]:
    played = max(1, team.played)
    recent = team.recent_points[-5:]
    return {
        "form": round(sum(recent) / max(1, len(recent) * 3), 4),
        "attack": round(team.goals_for / played, 4),
        "defense": round(team.goals_against / played, 4),
        "points_per_game": round(team.points / played, 4),
        "home_ppg": round(team.home_points / max(1, team.home_played), 4),
        "away_ppg": round(team.away_points / max(1, team.away_played), 4),
        "cards": team.cards,
        "suspensions": team.suspensions,
        "sample_size": team.played,
    }


def h2h_features(results: list[tuple[int, int]], limit: int = 5) -> dict[str, float | int]:
    recent = results[-limit:]
    if not recent:
        return {"home_rate": .3333, "draw_rate": .3333, "away_rate": .3334, "sample_size": 0}
    counts = {"1": 0, "X": 0, "2": 0}
    for home, away in recent:
        counts["1" if home > away else "2" if away > home else "X"] += 1
    return {"home_rate": counts["1"] / len(recent), "draw_rate": counts["X"] / len(recent), "away_rate": counts["2"] / len(recent), "sample_size": len(recent)}


def table_position(points: dict[str, int], goals: dict[str, tuple[int, int]], team: str) -> int | None:
    if team not in points:
        return None
    ordered = sorted(points, key=lambda name: (points[name], goals.get(name, (0, 0))[0] - goals.get(name, (0, 0))[1], goals.get(name, (0, 0))[0]), reverse=True)
    return ordered.index(team) + 1

