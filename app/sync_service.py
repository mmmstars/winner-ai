import os
import threading
from datetime import datetime, timezone

from app.database import bootstrap_team_ratings, import_external_odds, import_fixture_absences, import_matches, import_team_metrics, import_teams, settle_ready_runs
from app.providers import (
    api_football_configured,
    api_football_fixtures,
    api_football_israel_leagues,
    api_football_odds,
    api_football_absences,
    api_football_team_metrics,
    football_data_configured,
    football_data_matches,
    football_data_teams,
    openliga_matches,
)
from app.round_service import create_automatic_round
from app.israel_data import public_israel_data
from app.backup import create_backup


DEFAULT_COMPETITIONS = "PL,PD,BL1,SA,FL1,DED,PPL,CL"
OPENLIGA_COMPETITIONS = ("bl1", "bl2")
_lock = threading.Lock()
_started = False
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
        "api_football": api_football_configured(),
        "football_data": football_data_configured(),
        "openligadb": True,
        "public_israel": True,
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
        teams_total += import_teams(israel_teams, "public-israel")
        matches_total += import_matches(israel_matches, "public-israel")
        import_external_odds(israel_matches, "public-israel")
    except Exception as error:
        errors.append(f"ישראל ציבורי: {type(error).__name__}")
    use_api_football_current = os.getenv("API_FOOTBALL_USE_CURRENT", "false").lower() == "true"
    if api_football_configured() and use_api_football_current:
        try:
            api_matches = []
            league_details = {}
            for league in api_football_israel_leagues():
                teams, matches = api_football_fixtures(league["id"], league["season"])
                league_details[str(league["id"])] = league
                teams_total += import_teams(teams, "api-football")
                matches_total += import_matches(matches, "api-football")
                api_matches.extend(matches)
            odds = []
            selected = sorted(api_matches, key=lambda match: match["kickoff_at"])[:16]
            for item in selected:
                value = api_football_odds(item["external_id"])
                if value:
                    odds.append(value)
            import_external_odds(odds, "api-football")
            metric_keys = {}
            for item in selected:
                league = league_details.get(item["competition"])
                if league:
                    for key in ("home_external_id", "away_external_id"):
                        metric_keys[item[key]] = league
                import_fixture_absences(
                    item["external_id"],
                    api_football_absences(item["external_id"]),
                    "api-football",
                )
            metrics = [
                api_football_team_metrics(team_id, league["id"], league["season"])
                for team_id, league in metric_keys.items()
            ]
            import_team_metrics(metrics, "api-football")
        except RuntimeError as error:
            errors.append(f"ישראל: {error}")
    if football_data_configured():
        for competition in configured_competitions():
            try:
                teams_total += import_teams(football_data_teams(competition), "football-data.org")
                matches_total += import_matches(football_data_matches(competition), "football-data.org")
            except RuntimeError as error:
                errors.append(f"{competition}: {error}")
    season = datetime.now(timezone.utc).year
    for competition in OPENLIGA_COMPETITIONS:
        try:
            previous_teams, _, previous_metrics = openliga_matches(competition, season - 1)
            teams_total += import_teams(previous_teams, "openligadb")
            import_team_metrics(previous_metrics, "openligadb")
            teams, matches, metrics = openliga_matches(competition, season)
            teams_total += import_teams(teams, "openligadb")
            matches_total += import_matches(matches, "openligadb")
            import_team_metrics(metrics, "openligadb")
        except RuntimeError as error:
            errors.append(f"{competition.upper()}: {error}")
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
    if _started:
        return False
    _started = True
    threading.Thread(target=_worker, name="football-data-sync", daemon=True).start()
    return True
