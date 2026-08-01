from datetime import datetime, timezone

from app.prediction import GameInput


def parse_coupon(text: str) -> list[GameInput]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 16:
        raise ValueError("יש להזין בדיוק 16 משחקים.")
    games = []
    for number, line in enumerate(lines, 1):
        parts = [part.strip() for part in line.replace(" – ", "|").split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise ValueError(f"שורה {number} אינה תקינה. יש לכתוב: קבוצת בית | קבוצת חוץ")
        odds = [2.5, 3.2, 2.8]
        if len(parts) >= 5:
            try:
                odds = [float(value) for value in parts[2:5]]
            except ValueError as error:
                raise ValueError(f"היחסים בשורה {number} אינם תקינים.") from error
        games.append(GameInput(
            number=number,
            home_team=parts[0], away_team=parts[1],
            home_odds=odds[0], draw_odds=odds[1], away_odds=odds[2],
            kickoff_at=datetime.now(timezone.utc), provider="manual",
        ))
    return games
