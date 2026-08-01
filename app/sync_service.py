import os
import threading
from datetime import datetime, timezone

from app.database import import_matches, import_teams
from app.providers import football_data_configured, football_data_matches, football_data_teams


DEFAULT_COMPETITIONS = "PL,PD,BL1,SA,FL1,DED,PPL,CL"
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
}


def configured_competitions() -> list[str]:
    raw = os.getenv("FOOTBALL_DATA_COMPETITIONS", DEFAULT_COMPETITIONS)
    return list(dict.fromkeys(code.strip().upper() for code in raw.split(",") if code.strip()))


def sync_status() -> dict:
    with _lock:
        result = dict(_status)
        result["errors"] = list(_status["errors"])
    result["configured"] = football_data_configured()
    result["competitions"] = configured_competitions()
    return result


def sync_all() -> dict:
    started = datetime.now(timezone.utc).isoformat()
    with _lock:
        _status.update(running=True, configured=football_data_configured(), last_started_at=started, errors=[])
    teams_total = 0
    matches_total = 0
    errors = []
    if not football_data_configured():
        errors.append("חסר FOOTBALL_DATA_TOKEN")
    else:
        for competition in configured_competitions():
            try:
                teams_total += import_teams(football_data_teams(competition), "football-data.org")
                matches_total += import_matches(football_data_matches(competition), "football-data.org")
            except RuntimeError as error:
                errors.append(f"{competition}: {error}")
    with _lock:
        _status.update(
            running=False,
            last_finished_at=datetime.now(timezone.utc).isoformat(),
            teams_imported=teams_total,
            matches_imported=matches_total,
            errors=errors,
        )
    return sync_status()


def _worker() -> None:
    interval = max(15, int(os.getenv("FOOTBALL_DATA_SYNC_MINUTES", "180"))) * 60
    while True:
        sync_all()
        threading.Event().wait(interval)


def start_auto_sync() -> bool:
    global _started
    if _started or not football_data_configured():
        return False
    _started = True
    threading.Thread(target=_worker, name="football-data-sync", daemon=True).start()
    return True
