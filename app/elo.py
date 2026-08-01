import math


HOME_ADVANTAGE = 65.0


def expected_home_score(home_rating: float, away_rating: float) -> float:
    difference = away_rating - (home_rating + HOME_ADVANTAGE)
    return 1.0 / (1.0 + math.pow(10.0, difference / 400.0))


def elo_probabilities(home_rating: float, away_rating: float) -> dict[str, float]:
    home_strength = expected_home_score(home_rating, away_rating)
    closeness = 1.0 - abs(home_strength - 0.5) * 2.0
    draw = 0.18 + 0.10 * max(0.0, closeness)
    decisive = 1.0 - draw
    home = decisive * home_strength
    away = decisive * (1.0 - home_strength)
    total = home + draw + away
    return {"1": home / total, "X": draw / total, "2": away / total}


def update_elo(home_rating: float, away_rating: float, result: str, goal_difference: int, k: float = 24.0) -> tuple[float, float]:
    expected = expected_home_score(home_rating, away_rating)
    actual = {"1": 1.0, "X": 0.5, "2": 0.0}[result]
    multiplier = 1.0 + math.log1p(max(0, abs(goal_difference) - 1))
    change = k * multiplier * (actual - expected)
    return round(home_rating + change, 2), round(away_rating - change, 2)
