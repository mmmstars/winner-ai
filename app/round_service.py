from datetime import date

from app.database import create_round, round_id_by_name, upcoming_matches
from app.prediction import GameInput, market_analysis


def create_automatic_round() -> int | None:
    name = f"מחזור אוטומטי {date.today().strftime('%d.%m.%Y')}"
    existing = round_id_by_name(name)
    if existing:
        return existing
    candidates = [item for item in upcoming_matches(100) if valid_odds(item)]
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
        )
        for index, item in enumerate(unique, start=1)
    ]
    closes_at = min(item["kickoff_at"] for item in unique)
    return create_round(name, closes_at, games, [market_analysis(game) for game in games])


def valid_odds(item: dict) -> bool:
    return all(item.get(key) is not None and float(item[key]) > 1 for key in ("home_odds", "draw_odds", "away_odds"))
