from datetime import datetime
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


def probabilities(game: GameInput) -> dict[str, float]:
    raw = {"1": 1 / game.home_odds, "X": 1 / game.draw_odds, "2": 1 / game.away_odds}
    total = sum(raw.values())
    return {key: round(value / total, 4) for key, value in raw.items()}


def market_analysis(game: GameInput) -> dict:
    implied = {"1": 1 / game.home_odds, "X": 1 / game.draw_odds, "2": 1 / game.away_odds}
    overround = sum(implied.values())
    fair = probabilities(game)
    return {
        "game_number": game.number,
        "implied": {key: round(value, 4) for key, value in implied.items()},
        "fair": fair,
        "bookmaker_margin": round((overround - 1) * 100, 2),
        "method": "simple_normalization",
        "model": prediction_probabilities(game),
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
    combined = {
        key: market[key] * 0.45 + elo[key] * 0.20 + goals[key] * 0.20 + factors[key] * 0.15
        for key in ("1", "X", "2")
    }
    total = sum(combined.values())
    return {key: round(value / total, 4) for key, value in combined.items()}


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
