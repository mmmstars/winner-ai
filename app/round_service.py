from datetime import date

from app.database import create_round, delete_round, round_id_by_name, upcoming_matches
from app.prediction import GameInput, market_analysis


def create_automatic_round() -> int | None:
    name = f"מחזור אוטומטי {date.today().strftime('%d.%m.%Y')}"
    existing = round_id_by_name(name)
    if existing:
        delete_round(existing)
    candidates = [prepare_odds(item) for item in upcoming_matches(100)]
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
            home_goals_for=item["home_goals_for"],
            home_goals_against=item["home_goals_against"],
            away_goals_for=item["away_goals_for"],
            away_goals_against=item["away_goals_against"],
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
    prepared.update(home_odds=2.35, draw_odds=3.20, away_odds=2.95, estimated_odds=True)
    return prepared
