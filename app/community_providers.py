"""Polite adapters for high-coverage free community data sources."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.team_names import hebrew_team_name, team_aliases

FOOTBALL_DATA_UK = "https://www.football-data.co.uk/mmz4281"
STATSBOMB_RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
THESPORTSDB = "https://www.thesportsdb.com/api/v1/json/123"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


def _read(url: str, timeout: int = 25) -> bytes:
    request = Request(url, headers={"User-Agent": "WinnerAI/1.1 (+free-source-cache)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as error:
        if error.code == 429:
            raise RuntimeError("המקור הגביל זמנית את קצב הבקשות") from error
        raise RuntimeError(f"המקור החזיר שגיאה {error.code}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError("המקור אינו זמין כרגע") from error


def football_data_uk(season: str, divisions: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
    teams: dict[str, dict] = {}
    matches, odds = [], []
    for division in divisions:
        content = _read(f"{FOOTBALL_DATA_UK}/{season}/{division}.csv").decode("utf-8-sig", errors="replace")
        for row_number, row in enumerate(csv.DictReader(io.StringIO(content)), start=2):
            home, away, match_date = (row.get("HomeTeam") or "").strip(), (row.get("AwayTeam") or "").strip(), (row.get("Date") or "").strip()
            if not home or not away or not match_date:
                continue
            try:
                played_at = datetime.strptime(match_date, "%d/%m/%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            external_id = f"{season}-{division}-{row_number}-{home}-{away}"
            for name in (home, away):
                teams[name] = {"external_id": name, "name_he": hebrew_team_name(name), "aliases": team_aliases(name, hebrew_team_name(name))}
            finished = row.get("FTHG", "").isdigit() and row.get("FTAG", "").isdigit()
            matches.append({"external_id": external_id, "competition": division.upper(), "kickoff_at": played_at.isoformat(), "status": "finished" if finished else "scheduled", "home_external_id": home, "away_external_id": away, "home_team": hebrew_team_name(home), "away_team": hebrew_team_name(away), "home_score": int(row["FTHG"]) if finished else None, "away_score": int(row["FTAG"]) if finished else None})
            prices = _best_1x2(row)
            if prices:
                odds.append({"external_id": external_id, **prices, "source": "football-data.co.uk-csv"})
    return list(teams.values()), matches, odds


def _best_1x2(row: dict) -> dict | None:
    for home, draw, away in (("AvgCH", "AvgCD", "AvgCA"), ("AvgH", "AvgD", "AvgA"), ("B365H", "B365D", "B365A")):
        try:
            values = [float(row[key]) for key in (home, draw, away)]
        except (KeyError, TypeError, ValueError):
            continue
        if all(value > 1 for value in values):
            return {"home_odds": values[0], "draw_odds": values[1], "away_odds": values[2]}
    return None


def statsbomb_matches(pairs: list[tuple[int, int]]) -> tuple[list[dict], list[dict]]:
    teams: dict[str, dict] = {}
    matches = []
    for competition_id, season_id in pairs:
        payload = json.loads(_read(f"{STATSBOMB_RAW}/matches/{competition_id}/{season_id}.json"))
        for item in payload:
            home, away = item.get("home_team", {}), item.get("away_team", {})
            if not home.get("home_team_name") or not away.get("away_team_name"):
                continue
            for side, prefix in ((home, "home"), (away, "away")):
                name, team_id = side[f"{prefix}_team_name"], str(side[f"{prefix}_team_id"])
                teams[team_id] = {"external_id": team_id, "name_he": hebrew_team_name(name), "aliases": team_aliases(name, hebrew_team_name(name))}
            kickoff = f"{item['match_date']}T{item.get('kick_off') or '00:00:00'}"
            matches.append({"external_id": str(item["match_id"]), "competition": f"SB-{competition_id}", "kickoff_at": kickoff, "status": "finished" if item.get("home_score") is not None else "scheduled", "home_external_id": str(home["home_team_id"]), "away_external_id": str(away["away_team_id"]), "home_team": hebrew_team_name(home["home_team_name"]), "away_team": hebrew_team_name(away["away_team_name"]), "home_score": item.get("home_score"), "away_score": item.get("away_score")})
    return list(teams.values()), matches


def thesportsdb_league_events(league_ids: list[str], season: str) -> tuple[list[dict], list[dict]]:
    teams: dict[str, dict] = {}
    matches = []
    for league_id in league_ids:
        payload = json.loads(_read(f"{THESPORTSDB}/eventsseason.php?{urlencode({'id': league_id, 's': season})}"))
        for item in payload.get("events") or []:
            home, away = item.get("strHomeTeam"), item.get("strAwayTeam")
            if not home or not away or not item.get("idEvent") or not item.get("dateEvent"):
                continue
            home_id, away_id = str(item.get("idHomeTeam") or home), str(item.get("idAwayTeam") or away)
            for team_id, name in ((home_id, home), (away_id, away)):
                teams[team_id] = {"external_id": team_id, "name_he": hebrew_team_name(name), "aliases": team_aliases(name, hebrew_team_name(name))}
            home_score, away_score = item.get("intHomeScore"), item.get("intAwayScore")
            matches.append({"external_id": str(item["idEvent"]), "competition": f"TSDB-{league_id}", "kickoff_at": f"{item['dateEvent']}T{item.get('strTime') or '00:00:00'}Z", "status": "finished" if home_score not in (None, "") else "scheduled", "home_external_id": home_id, "away_external_id": away_id, "home_team": hebrew_team_name(home), "away_team": hebrew_team_name(away), "home_score": int(home_score) if home_score not in (None, "") else None, "away_score": int(away_score) if away_score not in (None, "") else None})
    return list(teams.values()), matches


def open_meteo_weather(latitude: float, longitude: float, kickoff_at: str) -> dict:
    kickoff = datetime.fromisoformat(kickoff_at.replace("Z", "+00:00"))
    query = urlencode({"latitude": latitude, "longitude": longitude, "hourly": "temperature_2m,precipitation,wind_speed_10m", "timezone": "UTC", "start_date": kickoff.date().isoformat(), "end_date": kickoff.date().isoformat()})
    payload = json.loads(_read(f"{OPEN_METEO}?{query}"))
    hourly, target = payload.get("hourly", {}), kickoff.astimezone(timezone.utc).replace(tzinfo=None)
    times = hourly.get("time") or []
    if not times:
        raise RuntimeError("אין תחזית מזג אוויר למועד המשחק")
    index = min(range(len(times)), key=lambda i: abs((datetime.fromisoformat(times[i]) - target).total_seconds()))
    return {"temperature": float(hourly["temperature_2m"][index]), "precipitation": float(hourly["precipitation"][index]), "wind_speed": float(hourly["wind_speed_10m"][index]), "source": "open-meteo", "observed_at": datetime.now(timezone.utc).isoformat()}


def parse_pairs(value: str) -> list[tuple[int, int]]:
    return [(int(part.split(":", 1)[0]), int(part.split(":", 1)[1])) for part in value.split(",") if ":" in part]

