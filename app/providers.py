import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FOOTBALL_DATA_URL = "https://api.football-data.org/v4"


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
