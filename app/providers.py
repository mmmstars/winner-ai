import json
import os
from urllib.request import Request, urlopen


FOOTBALL_DATA_URL = "https://api.football-data.org/v4"


def football_data_teams(competition: str) -> list[dict]:
    token = os.getenv("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        raise RuntimeError("חסר FOOTBALL_DATA_TOKEN")
    code = competition.strip().upper()
    request = Request(
        f"{FOOTBALL_DATA_URL}/competitions/{code}/teams",
        headers={"X-Auth-Token": token, "User-Agent": "WinnerAI/1.0"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    return parse_football_data_teams(payload)


def football_data_matches(competition: str) -> list[dict]:
    token = os.getenv("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        raise RuntimeError("חסר FOOTBALL_DATA_TOKEN")
    code = competition.strip().upper()
    request = Request(
        f"{FOOTBALL_DATA_URL}/competitions/{code}/matches?status=SCHEDULED",
        headers={"X-Auth-Token": token, "User-Agent": "WinnerAI/1.0"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
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
