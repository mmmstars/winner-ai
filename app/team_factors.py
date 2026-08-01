def factor_probabilities(
    home_form: float,
    away_form: float,
    home_missing: int,
    away_missing: int,
) -> dict[str, float]:
    """Turn recent form and missing-player data into conservative 1/X/2 chances."""
    form_gap = max(-1.0, min(1.0, home_form - away_form))
    absence_gap = max(-8, min(8, away_missing - home_missing)) / 8
    advantage = form_gap * 0.7 + absence_gap * 0.3
    home = 0.40 + advantage * 0.16
    away = 0.30 - advantage * 0.16
    draw = 1.0 - home - away
    values = {"1": max(0.12, home), "X": max(0.18, draw), "2": max(0.12, away)}
    total = sum(values.values())
    return {key: round(value / total, 4) for key, value in values.items()}
