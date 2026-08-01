import os
import threading
import logging
import json
from datetime import datetime, timezone

from app.database import bootstrap_team_ratings, import_external_odds, import_fixture_absences, import_fixture_weather, import_matches, import_team_metrics, import_teams, settle_ready_runs, upcoming_matches
from app.providers import (
    football_data_configured,
    football_data_matches,
    football_data_teams,
    openliga_matches,
)
from app.round_service import create_automatic_round
from app.israel_data import public_israel_data
from app.backup import create_backup
from app.community_providers import football_data_uk, statsbomb_matches, thesportsdb_league_events, open_meteo_weather, parse_pairs
from app.normalization import normalized_name


DEFAULT_COMPETITIONS = "PL,PD,BL1,SA,FL1,DED,PPL,CL"
OPENLIGA_COMPETITIONS = ("bl1", "bl2")
_lock = threading.Lock()
_started = False
logger = logging.getLogger("winner_ai.sync")
_status = {
    "running": False,
    "configured": False,
    "last_started_at": None,
    "last_finished_at": None,
    "teams_imported": 0,
    "matches_imported": 0,
    "errors": [],
    "round_id": None,
    "historical_ratings_built": 0,
}


def configured_competitions() -> list[str]:
    raw = os.getenv("FOOTBALL_DATA_COMPETITIONS", DEFAULT_COMPETITIONS)
    return list(dict.fromkeys(code.strip().upper() for code in raw.split(",") if code.strip()))


def sync_status() -> dict:
    with _lock:
        result = dict(_status)
        result["errors"] = list(_status["errors"])
    result["configured"] = True
    result["providers"] = {
        "football_data": football_data_configured(),
        "openligadb": True,
        "public_israel": True,
        "football_data_uk": True,
        "statsbomb_open": True,
        "thesportsdb": True,
        "open_meteo": bool(os.getenv("VENUE_COORDINATES_JSON", "").strip()),
    }
    result["competitions"] = configured_competitions()
    return result


def sync_all() -> dict:
    started = datetime.now(timezone.utc).isoformat()
    with _lock:
        _status.update(running=True, configured=True, last_started_at=started, errors=[])
    teams_total = 0
    matches_total = 0
    errors = []
    try:
        israel_teams, israel_matches = public_israel_data()
        teams_total += import_teams(israel_teams, "public-israel-estimate")
        matches_total += import_matches(israel_matches, "public-israel-estimate")
    except Exception as error:
        logger.exception("public Israel demo import failed")
        errors.append(f"ישראל ציבורי: {type(error).__name__}")
    if football_data_configured():
        for competition in configured_competitions():
            try:
                teams_total += import_teams(football_data_teams(competition), "football-data.org")
                matches_total += import_matches(football_data_matches(competition), "football-data.org")
            except RuntimeError as error:
                logger.warning("football-data.org sync failed for %s: %s", competition, error)
                errors.append(f"{competition}: {error}")
    try:
        season_code = os.getenv("FOOTBALL_DATA_UK_SEASON", "2526").strip()
        divisions = [item.strip() for item in os.getenv("FOOTBALL_DATA_UK_DIVISIONS", "E0,D1,SP1,I1,F1").split(",") if item.strip()]
        teams, matches, odds = football_data_uk(season_code, divisions)
        teams_total += import_teams(teams, "football-data.co.uk")
        matches_total += import_matches(matches, "football-data.co.uk")
        import_external_odds(odds, "football-data.co.uk")
    except RuntimeError as error:
        logger.warning("Football-Data.co.uk sync failed: %s", error)
        errors.append(f"Football-Data.co.uk: {error}")
    try:
        pairs = parse_pairs(os.getenv("STATSBOMB_COMPETITION_SEASONS", "223:282"))
        teams, matches = statsbomb_matches(pairs)
        teams_total += import_teams(teams, "statsbomb-open")
        matches_total += import_matches(matches, "statsbomb-open")
    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
        logger.warning("StatsBomb sync failed: %s", error)
        errors.append(f"StatsBomb: {error}")
    try:
        league_ids = [item.strip() for item in os.getenv("THESPORTSDB_LEAGUE_IDS", "4328,4335").split(",") if item.strip()]
        season_name = os.getenv("THESPORTSDB_SEASON", "2026-2027")
        teams, matches = thesportsdb_league_events(league_ids, season_name)
        teams_total += import_teams(teams, "thesportsdb")
        matches_total += import_matches(matches, "thesportsdb")
    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
        logger.warning("TheSportsDB sync failed: %s", error)
        errors.append(f"TheSportsDB: {error}")
    season = datetime.now(timezone.utc).year
    for competition in OPENLIGA_COMPETITIONS:
        try:
            previous_teams, previous_matches, previous_metrics = openliga_matches(competition, season - 1)
            teams_total += import_teams(previous_teams, "openligadb")
            matches_total += import_matches(previous_matches, "openligadb")
            import_team_metrics(previous_metrics, "openligadb")
            teams, matches, metrics = openliga_matches(competition, season)
            teams_total += import_teams(teams, "openligadb")
            matches_total += import_matches(matches, "openligadb")
            import_team_metrics(metrics, "openligadb")
        except RuntimeError as error:
            logger.warning("OpenLigaDB sync failed for %s: %s", competition, error)
            errors.append(f"{competition.upper()}: {error}")
    try:
        venue_coordinates = json.loads(os.getenv("VENUE_COORDINATES_JSON", "{}"))
        weather_count = 0
        for item in upcoming_matches(40):
            coordinates = venue_coordinates.get(normalized_name(item["home_team"]))
            if not coordinates:
                continue
            weather = open_meteo_weather(float(coordinates[0]), float(coordinates[1]), item["kickoff_at"])
            import_fixture_weather(item["external_id"], weather, item["provider"])
            weather_count += 1
        logger.info("Open-Meteo updated %s fixtures", weather_count)
    except (RuntimeError, ValueError, TypeError, json.JSONDecodeError) as error:
        logger.warning("Open-Meteo sync failed: %s", error)
        errors.append(f"Open-Meteo: {error}")
    historical_ratings_built = bootstrap_team_ratings()
    round_id = create_automatic_round()
    settle_ready_runs()
    try:
        create_backup()
    except OSError as error:
        errors.append(f"גיבוי: {type(error).__name__}")
    with _lock:
        _status.update(
            running=False,
            last_finished_at=datetime.now(timezone.utc).isoformat(),
            teams_imported=teams_total,
            matches_imported=matches_total,
            errors=errors,
            round_id=round_id,
            historical_ratings_built=historical_ratings_built,
        )
    return sync_status()


def _worker() -> None:
    interval = max(60, int(os.getenv("FOOTBALL_DATA_SYNC_MINUTES", "1440"))) * 60
    while True:
        try:
            sync_all()
        except Exception as error:
            with _lock:
                _status.update(
                    running=False,
                    last_finished_at=datetime.now(timezone.utc).isoformat(),
                    errors=[f"שגיאת סנכרון: {type(error).__name__}"],
                )
        threading.Event().wait(interval)


def start_auto_sync() -> bool:
    global _started
    if os.getenv("AUTO_SYNC_ENABLED", "true").lower() != "true":
        return False
    if _started:
        return False
    _started = True
    threading.Thread(target=_worker, name="football-data-sync", daemon=True).start()
    return True
