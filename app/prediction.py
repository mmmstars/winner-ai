from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.elo import elo_probabilities
from app.poisson import dixon_coles_probabilities
from app.ticket_optimizer import optimize
from app.team_factors import factor_probabilities


Selection = Literal["1", "X", "2"]


class GameInput(BaseModel):
    number: int = Field(ge=1, le=16)
    home_team: str = Field(min_length=1, max_length=100)
    away_team: str = Field(min_length=1, max_length=100)
    home_odds: float = Field(gt=1, le=100)
    draw_odds: float = Field(gt=1, le=100)
    away_odds: float = Field(gt=1, le=100)
    home_elo: float = Field(default=1500, ge=500, le=3000)
    away_elo: float = Field(default=1500, ge=500, le=3000)
    home_goals_for: float = Field(default=1.4, ge=0, le=10)
    home_goals_against: float = Field(default=1.2, ge=0, le=10)
    away_goals_for: float = Field(default=1.2, ge=0, le=10)
    away_goals_against: float = Field(default=1.4, ge=0, le=10)
    home_form: float = Field(default=0.5, ge=0, le=1)
    away_form: float = Field(default=0.5, ge=0, le=1)
    home_missing: int = Field(default=0, ge=0, le=20)
    away_missing: int = Field(default=0, ge=0, le=20)
    home_table_position: int | None = Field(default=None, ge=1, le=100)
    away_table_position: int | None = Field(default=None, ge=1, le=100)
    h2h_home_rate: float = Field(default=.3333, ge=0, le=1)
    h2h_draw_rate: float = Field(default=.3333, ge=0, le=1)
    h2h_away_rate: float = Field(default=.3334, ge=0, le=1)
    h2h_matches: int = Field(default=0, ge=0)
    history_matches: int = Field(default=0, ge=0)
    odds_are_estimated: bool = False
    home_cards: int | None = Field(default=None, ge=0, le=100)
    away_cards: int | None = Field(default=None, ge=0, le=100)
    temperature: float | None = Field(default=None, ge=-30, le=60)
    precipitation: float | None = Field(default=None, ge=0, le=500)
    wind_speed: float | None = Field(default=None, ge=0, le=250)
    kickoff_at: datetime | None = None
    provider: str = "manual"
    external_match_id: str = ""


class GenerateRequest(BaseModel):
    games: list[GameInput]
    ticket_count: int = Field(ge=1, le=20)
    strategy: Literal["בטוח", "מאוזן", "נועז"]

    @model_validator(mode="after")
    def validate_games(self):
        if len(self.games) != 16:
            raise ValueError("יש להזין בדיוק 16 משחקים")
        if sorted(game.number for game in self.games) != list(range(1, 17)):
            raise ValueError("מספרי המשחקים חייבים להיות 1 עד 16")
        return self


class RoundRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    closes_at: datetime
    games: list[GameInput]

    @model_validator(mode="after")
    def validate_round(self):
        if len(self.games) != 16:
            raise ValueError("מחזור Winner חייב לכלול בדיוק 16 משחקים")
        if sorted(game.number for game in self.games) != list(range(1, 17)):
            raise ValueError("מספרי המשחקים חייבים להיות 1 עד 16")
        pairs = {(game.home_team.casefold(), game.away_team.casefold()) for game in self.games}
        if len(pairs) != 16:
            raise ValueError("נמצאו משחקים כפולים")
        return self


class SettleRequest(BaseModel):
    results: list[Selection]

    @model_validator(mode="after")
    def validate_results(self):
        if len(self.results) != 16:
            raise ValueError("יש להזין בדיוק 16 תוצאות")
        return self


class TeamImport(BaseModel):
    external_id: str = ""
    name_he: str = Field(min_length=1, max_length=150)
    aliases: list[str] = []


class TeamImportRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    teams: list[TeamImport] = Field(min_length=1, max_length=5000)


class SourceImportRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2_000_000)
    format: Literal["official_csv", "openfootball_json"] = "official_csv"


def probabilities(game: GameInput) -> dict[str, float]:
    raw = {"1": 1 / game.home_odds, "X": 1 / game.draw_odds, "2": 1 / game.away_odds}
    total = sum(raw.values())
    return {key: round(value / total, 4) for key, value in raw.items()}


def market_analysis(game: GameInput) -> dict:
    implied = {"1": 1 / game.home_odds, "X": 1 / game.draw_odds, "2": 1 / game.away_odds}
    overround = sum(implied.values())
    fair = probabilities(game)
    model = prediction_probabilities(game)
    value = {key: round(model[key] * odd - 1, 4) for key, odd in zip(("1", "X", "2"), (game.home_odds, game.draw_odds, game.away_odds))}
    best = max(model, key=model.get)
    ordered = sorted(model.values(), reverse=True)
    history_quality = min(1.0, game.history_matches / 20)
    source_quality = .55 if game.odds_are_estimated else 1.0
    data_quality = round((history_quality * .75 + min(1, game.h2h_matches / 5) * .25) * source_quality, 3)
    confidence = round(max(0, min(100, (45 + (ordered[0] - ordered[1]) * 100) * (.65 + .35 * data_quality))), 1)
    return {
        "game_number": game.number,
        "implied": {key: round(value, 4) for key, value in implied.items()},
        "fair": fair,
        "bookmaker_margin": round((overround - 1) * 100, 2),
        "method": "simple_normalization",
        "model": model,
        "prediction": best,
        "confidence": confidence,
        "data_quality": data_quality,
        "hours_to_kickoff": hours_to_kickoff(game),
        "value": value,
        "value_selections": [key for key in ("1", "X", "2") if value[key] >= .05],
    }


def prediction_probabilities(game: GameInput) -> dict[str, float]:
    market = probabilities(game)
    elo = elo_probabilities(game.home_elo, game.away_elo)
    goals = dixon_coles_probabilities(
        game.home_goals_for,
        game.home_goals_against,
        game.away_goals_for,
        game.away_goals_against,
    )
    factors = factor_probabilities(
        game.home_form,
        game.away_form,
        game.home_missing,
        game.away_missing,
    )
    position_gap = 0.0
    if game.home_table_position and game.away_table_position:
        position_gap = max(-1.0, min(1.0, (game.away_table_position - game.home_table_position) / 12))
    h2h_total = max(.0001, game.h2h_home_rate + game.h2h_draw_rate + game.h2h_away_rate)
    context = {
        "1": max(.05, game.h2h_home_rate / h2h_total + position_gap * .08),
        "X": max(.05, game.h2h_draw_rate / h2h_total),
        "2": max(.05, game.h2h_away_rate / h2h_total - position_gap * .08),
    }
    context_total = sum(context.values())
    context = {key: value / context_total for key, value in context.items()}
    hours = hours_to_kickoff(game)
    proximity = 0.0 if hours is None else max(0.0, min(1.0, 1 - hours / (21 * 24)))
    if game.odds_are_estimated:
        weights = {"market": .08, "elo": .32 - .04 * proximity, "goals": .30,
                   "factors": .20 + .04 * proximity, "context": .10}
    else:
        weights = {"market": .38 + .05 * proximity, "elo": .20 - .03 * proximity,
                   "goals": .20, "factors": .14 + .02 * proximity, "context": .08 - .04 * proximity}
    combined = {
        key: market[key] * weights["market"] + elo[key] * weights["elo"] + goals[key] * weights["goals"]
        + factors[key] * weights["factors"] + context[key] * weights["context"]
        for key in ("1", "X", "2")
    }
    # Weather is intentionally a small modifier: only clearly severe conditions matter.
    severe_weather = (game.precipitation or 0) >= 5 or (game.wind_speed or 0) >= 35 or (game.temperature or 20) >= 35
    if severe_weather:
        combined["X"] += .025
        combined["1"] -= .0125
        combined["2"] -= .0125
    total = sum(combined.values())
    return {key: round(value / total, 4) for key, value in combined.items()}


def hours_to_kickoff(game: GameInput) -> float | None:
    if game.kickoff_at is None:
        return None
    kickoff = game.kickoff_at
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    return round(max(0.0, (kickoff - datetime.now(timezone.utc)).total_seconds() / 3600), 2)


def power_probabilities(game: GameInput) -> dict[str, float]:
    implied = {"1": 1 / game.home_odds, "X": 1 / game.draw_odds, "2": 1 / game.away_odds}
    low, high = 0.01, 10.0
    for _ in range(80):
        exponent = (low + high) / 2
        total = sum(value**exponent for value in implied.values())
        if total > 1:
            low = exponent
        else:
            high = exponent
    fair = {key: value**high for key, value in implied.items()}
    total = sum(fair.values())
    return {key: round(value / total, 4) for key, value in fair.items()}


def generate(request: GenerateRequest, seed: int) -> list[dict]:
    rows = [prediction_probabilities(game) for game in request.games]
    signatures = optimize(rows, request.ticket_count, request.strategy, seed)
    tickets = []
    for number, signature in enumerate(signatures, start=1):
        picks = []
        for game, chances, selection in zip(request.games, rows, signature):
            margin = sorted(chances.values(), reverse=True)
            picks.append({"game_number": game.number, "selection": selection, "confidence": round(50 + (margin[0] - margin[1]) * 100, 1), "probabilities": chances})
        tickets.append({"number": number, "picks": picks})
    return tickets
