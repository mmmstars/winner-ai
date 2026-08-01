import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.database import export_database


def create_backup() -> str:
    directory = Path(os.getenv("BACKUP_DIR", "/data/backups"))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"winner-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(export_database(), ensure_ascii=False), encoding="utf-8")
    backups = sorted(directory.glob("winner-*.json"), reverse=True)
    for old in backups[14:]:
        old.unlink(missing_ok=True)
    return str(path)
