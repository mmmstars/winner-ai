import math


def poisson_probability(goals: int, expected_goals: float) -> float:
    value = max(0.05, min(expected_goals, 5.0))
    return math.exp(-value) * value**goals / math.factorial(goals)


def expected_goals(home_for: float, home_against: float, away_for: float, away_against: float) -> tuple[float, float]:
    home = max(0.2, (home_for + away_against) / 2.0 + 0.18)
    away = max(0.2, (away_for + home_against) / 2.0 - 0.08)
    return min(home, 4.5), min(away, 4.5)


def poisson_probabilities(home_for: float, home_against: float, away_for: float, away_against: float) -> dict[str, float]:
    return dixon_coles_probabilities(home_for, home_against, away_for, away_against, rho=0.0)


def dixon_coles_probabilities(home_for: float, home_against: float, away_for: float, away_against: float, rho: float = -0.08) -> dict[str, float]:
    home_xg, away_xg = expected_goals(home_for, home_against, away_for, away_against)
    outcomes = {"1": 0.0, "X": 0.0, "2": 0.0}
    for home_goals in range(8):
        for away_goals in range(8):
            chance = poisson_probability(home_goals, home_xg) * poisson_probability(away_goals, away_xg)
            chance *= low_score_correction(home_goals, away_goals, home_xg, away_xg, rho)
            key = "1" if home_goals > away_goals else "2" if home_goals < away_goals else "X"
            outcomes[key] += chance
    total = sum(outcomes.values())
    return {key: value / total for key, value in outcomes.items()}


def low_score_correction(home_goals: int, away_goals: int, home_xg: float, away_xg: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return max(0.01, 1.0 - home_xg * away_xg * rho)
    if home_goals == 0 and away_goals == 1:
        return max(0.01, 1.0 + home_xg * rho)
    if home_goals == 1 and away_goals == 0:
        return max(0.01, 1.0 + away_xg * rho)
    if home_goals == 1 and away_goals == 1:
        return max(0.01, 1.0 - rho)
    return 1.0
