import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.team_names import hebrew_team_name, team_aliases


FOOTBALL_DATA_URL = "https://api.football-data.org/v4"
API_FOOTBALL_URL = "https://v3.football.api-sports.io"


def football_data_configured() -> bool:
    return bool(os.getenv("FOOTBALL_DATA_TOKEN", "").strip())


def football_data_request(path: str) -> dict:
    token = os.getenv("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        raise RuntimeError("חסר FOOTBALL_DATA_TOKEN")
    request = Request(
        f"{FOOTBALL_DATA_URL}{path}",
        headers={"X-Auth-Token": token, "User-Agent": "WinnerAI/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 403:
            raise RuntimeError("אין הרשאה לתחרות הזאת בחבילת football-data.org") from error
        if error.code == 429:
            raise RuntimeError("מכסת הבקשות ל-football-data.org הסתיימה זמנית") from error
        raise RuntimeError(f"football-data.org החזיר שגיאה {error.code}") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("לא ניתן להתחבר כרגע ל-football-data.org") from error


def api_football_configured() -> bool:
    return bool(os.getenv("API_FOOTBALL_KEY", "").strip())


def api_football_request(path: str, params: dict[str, object]) -> dict:
    token = os.getenv("API_FOOTBALL_KEY", "").strip()
    if not token:
        raise RuntimeError("חסר API_FOOTBALL_KEY")
    request = Request(
        f"{API_FOOTBALL_URL}{path}?{urlencode(params)}",
        headers={"x-apisports-key": token, "User-Agent": "WinnerAI/1.0"},
    )
    try:
        with urlopen(request, timeout=25) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 429:
            raise RuntimeError("מכסת הבקשות ל-API-Football הסתיימה זמנית") from error
        raise RuntimeError(f"API-Football החזיר שגיאה {error.code}") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("לא ניתן להתחבר כרגע ל-API-Football") from error
    errors = payload.get("errors")
    if errors:
        message = ", ".join(str(value) for value in errors.values()) if isinstance(errors, dict) else str(errors)
        raise RuntimeError(f"API-Football: {message}")
    return payload


def api_football_israel_leagues() -> list[dict]:
    payload = api_football_request("/leagues", {"country": "Israel", "current": "true"})
    leagues = []
    for item in payload.get("response", []):
        seasons = [season for season in item.get("seasons", []) if season.get("current")]
        league = item.get("league", {})
        if league.get("id") is not None and seasons:
            leagues.append({"id": int(league["id"]), "name": league.get("name", ""), "season": seasons[0]["year"]})
    return leagues


def api_football_fixtures(league_id: int, season: int, limit: int = 30) -> tuple[list[dict], list[dict]]:
    payload = api_football_request("/fixtures", {"league": league_id, "season": season, "next": limit})
    return parse_api_football_fixtures(payload, str(league_id))


def parse_api_football_fixtures(payload: dict, competition: str) -> tuple[list[dict], list[dict]]:
    teams_by_id = {}
    matches = []
    for item in payload.get("response", []):
        fixture = item.get("fixture", {})
        sides = item.get("teams", {})
        home, away = sides.get("home", {}), sides.get("away", {})
        if fixture.get("id") is None or not fixture.get("date") or not home.get("name") or not away.get("name"):
            continue
        for team in (home, away):
            if team.get("id") is not None:
                teams_by_id[str(team["id"])] = {"external_id": str(team["id"]), "name_he": hebrew_team_name(team["name"]), "aliases": team_aliases(team["name"], hebrew_team_name(team["name"]))}
        matches.append({
            "external_id": str(fixture["id"]),
            "competition": competition,
            "kickoff_at": fixture["date"],
            "status": fixture.get("status", {}).get("short", "NS").lower(),
            "home_external_id": str(home.get("id", "")),
            "home_team": hebrew_team_name(home["name"]),
            "away_external_id": str(away.get("id", "")),
            "away_team": hebrew_team_name(away["name"]),
        })
    return list(teams_by_id.values()), matches


def football_data_teams(competition: str) -> list[dict]:
    code = competition.strip().upper()
    payload = football_data_request(f"/competitions/{code}/teams")
    return parse_football_data_teams(payload)


def football_data_matches(competition: str) -> list[dict]:
    code = competition.strip().upper()
    payload = football_data_request(f"/competitions/{code}/matches?status=SCHEDULED")
    return parse_football_data_matches(payload, code)


def parse_football_data_teams(payload: dict) -> list[dict]:
    teams = []
    for item in payload.get("teams", []):
        name = item.get("shortName") or item.get("name")
        if not name or item.get("id") is None:
            continue
        aliases = list(dict.fromkeys(filter(None, [item.get("name"), item.get("shortName"), item.get("tla")])))
        teams.append({"external_id": str(item["id"]), "name_he": name, "aliases": aliases})
    return teams


def parse_football_data_matches(payload: dict, competition: str) -> list[dict]:
    matches = []
    for item in payload.get("matches", []):
        home, away = item.get("homeTeam", {}), item.get("awayTeam", {})
        if item.get("id") is None or not item.get("utcDate") or not home.get("name") or not away.get("name"):
            continue
        matches.append({
            "external_id": str(item["id"]),
            "competition": competition,
            "kickoff_at": item["utcDate"],
            "status": item.get("status", "SCHEDULED").lower(),
            "home_external_id": str(home.get("id", "")),
            "home_team": home.get("shortName") or home["name"],
            "away_external_id": str(away.get("id", "")),
            "away_team": away.get("shortName") or away["name"],
        })
    return matches
