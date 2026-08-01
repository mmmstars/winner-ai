from datetime import date

from app.database import create_round, delete_round, round_id_by_name, team_rating, upcoming_matches
from app.prediction import GameInput, market_analysis


ISRAELI_COMPETITIONS = {"TSDB-4644", "TSDB-4966"}
ISRAELI_PROVIDERS = {"official-israel-import", "thesportsdb-israel"}


def is_israeli_match(item: dict) -> bool:
    """Return true only for verified Israeli league/import records."""
    return (
        item.get("provider") in ISRAELI_PROVIDERS
        or item.get("competition") in ISRAELI_COMPETITIONS
    )


def create_automatic_round() -> int | None:
    name = f"מחזור אוטומטי {date.today().strftime('%d.%m.%Y')}"
    existing = round_id_by_name(name)
    if existing:
        delete_round(existing)
    candidates = [
        prepare_odds(item)
        for item in upcoming_matches(250)
        if is_israeli_match(item)
    ]
    candidates.sort(key=lambda item: item["kickoff_at"])
    unique = []
    seen = set()
    for item in candidates:
        pair = (item["home_team"].casefold(), item["away_team"].casefold())
        if pair not in seen:
            seen.add(pair)
            unique.append(item)
        if len(unique) == 16:
            break
    if len(unique) != 16:
        return None
    games = [
        GameInput(
            number=index,
            home_team=item["home_team"],
            away_team=item["away_team"],
            home_odds=item["home_odds"],
            draw_odds=item["draw_odds"],
            away_odds=item["away_odds"],
            home_form=item["home_form"],
            away_form=item["away_form"],
            home_missing=item["home_missing"],
            away_missing=item["away_missing"],
            temperature=item.get("temperature"),
            precipitation=item.get("precipitation"),
            wind_speed=item.get("wind_speed"),
            home_goals_for=item["home_goals_for"],
            home_goals_against=item["home_goals_against"],
            away_goals_for=item["away_goals_for"],
            away_goals_against=item["away_goals_against"],
            home_elo=team_rating(item["home_team"]),
            away_elo=team_rating(item["away_team"]),
            kickoff_at=item["kickoff_at"],
            provider=(
                "thesportsdb-israel"
                if item.get("competition") in ISRAELI_COMPETITIONS
                else item.get("provider", "manual")
            ),
            external_match_id=item["external_id"],
        )
        for index, item in enumerate(unique, start=1)
    ]
    closes_at = min(item["kickoff_at"] for item in unique)
    return create_round(name, closes_at, games, [market_analysis(game) for game in games])


def valid_odds(item: dict) -> bool:
    return all(item.get(key) is not None and float(item[key]) > 1 for key in ("home_odds", "draw_odds", "away_odds"))


def prepare_odds(item: dict) -> dict:
    if valid_odds(item):
        return item
    prepared = dict(item)
    estimated = item.get("estimated_probabilities")
    if estimated and all(float(estimated.get(key, 0)) > 0 for key in ("1", "X", "2")):
        prepared.update(
            home_odds=round(1 / float(estimated["1"]), 3),
            draw_odds=round(1 / float(estimated["X"]), 3),
            away_odds=round(1 / float(estimated["2"]), 3),
            estimated_odds=True,
        )
        return prepared
    home_strength = item.get("home_form", 0.5) + 0.18 * (
        item.get("home_goals_for", 1.3) - item.get("home_goals_against", 1.3)
    )
    away_strength = item.get("away_form", 0.5) + 0.18 * (
        item.get("away_goals_for", 1.3) - item.get("away_goals_against", 1.3)
    )
    gap = home_strength - away_strength
    if gap > 0.12:
        chances = (0.50, 0.27, 0.23)
    elif gap < -0.12:
        chances = (0.23, 0.27, 0.50)
    else:
        chances = (0.36, 0.30, 0.34)
    prepared.update(
        home_odds=round(1 / chances[0], 3),
        draw_odds=round(1 / chances[1], 3),
        away_odds=round(1 / chances[2], 3),
        estimated_odds=True,
    )
    return prepared
