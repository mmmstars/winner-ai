import random
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Selection = Literal["1", "X", "2"]


class GameInput(BaseModel):
    number: int = Field(ge=1, le=16)
    home_team: str = Field(min_length=1, max_length=100)
    away_team: str = Field(min_length=1, max_length=100)
    home_odds: float = Field(gt=1, le=100)
    draw_odds: float = Field(gt=1, le=100)
    away_odds: float = Field(gt=1, le=100)


class GenerateRequest(BaseModel):
    games: list[GameInput]
    ticket_count: int = Field(ge=1, le=20)
    strategy: Literal["׳‘׳˜׳•׳—", "׳׳׳•׳–׳", "׳ ׳•׳¢׳–"]

    @model_validator(mode="after")
    def validate_games(self):
        if len(self.games) != 16:
            raise ValueError("׳™׳© ׳׳”׳–׳™׳ ׳‘׳“׳™׳•׳§ 16 ׳׳©׳—׳§׳™׳")
        if sorted(game.number for game in self.games) != list(range(1, 17)):
            raise ValueError("׳׳¡׳₪׳¨׳™ ׳”׳׳©׳—׳§׳™׳ ׳—׳™׳™׳‘׳™׳ ׳׳”׳™׳•׳× 1 ׳¢׳“ 16")
        return self


class RoundRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    closes_at: datetime
    games: list[GameInput]

    @model_validator(mode="after")
    def validate_round(self):
        if len(self.games) != 16:
            raise ValueError("׳׳—׳–׳•׳¨ Winner ׳—׳™׳™׳‘ ׳׳›׳׳•׳ ׳‘׳“׳™׳•׳§ 16 ׳׳©׳—׳§׳™׳")
        if sorted(game.number for game in self.games) != list(range(1, 17)):
            raise ValueError("׳׳¡׳₪׳¨׳™ ׳”׳׳©׳—׳§׳™׳ ׳—׳™׳™׳‘׳™׳ ׳׳”׳™׳•׳× 1 ׳¢׳“ 16")
        pairs = {(game.home_team.casefold(), game.away_team.casefold()) for game in self.games}
        if len(pairs) != 16:
            raise ValueError("׳ ׳׳¦׳׳• ׳׳©׳—׳§׳™׳ ׳›׳₪׳•׳׳™׳")
        return self


class SettleRequest(BaseModel):
    results: list[Selection]

    @model_validator(mode="after")
    def validate_results(self):
        if len(self.results) != 16:
            raise ValueError("׳™׳© ׳׳”׳–׳™׳ ׳‘׳“׳™׳•׳§ 16 ׳×׳•׳¦׳׳•׳×")
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
    }


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
    rng = random.Random(seed)
    variation = {"׳‘׳˜׳•׳—": 0.05, "׳׳׳•׳–׳": 0.16, "׳ ׳•׳¢׳–": 0.30}[request.strategy]
    tickets, used = [], set()
    for number in range(1, request.ticket_count + 1):
        for _ in range(100):
            picks = []
            for game in request.games:
                chances = probabilities(game)
                ordered = sorted(chances, key=chances.get, reverse=True)
                selection = ordered[0] if rng.random() > variation else rng.choices(ordered[1:], weights=[chances[key] for key in ordered[1:]])[0]
                margin = sorted(chances.values(), reverse=True)
                picks.append({"game_number": game.number, "selection": selection, "confidence": round(50 + (margin[0] - margin[1]) * 100, 1), "probabilities": chances})
            signature = tuple(pick["selection"] for pick in picks)
            if signature not in used or request.ticket_count == 1:
                used.add(signature)
                tickets.append({"number": number, "picks": picks})
                break
    return tickets

