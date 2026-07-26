import json
import os
import sqlite3
from datetime import date
from pathlib import Path

from app.data import HISTORY, TODAY_RECOMMENDATIONS


DB_PATH = Path(os.getenv("WINNER_DB_PATH", Path(__file__).resolve().parent.parent / "winner.db"))


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_date TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                match_time TEXT NOT NULL,
                pick TEXT NOT NULL,
                confidence TEXT NOT NULL,
                medal TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_date TEXT NOT NULL,
                match_name TEXT NOT NULL,
                pick TEXT NOT NULL,
                result TEXT NOT NULL,
                success INTEGER NOT NULL
            );
            """
        )
        if connection.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 0:
            for item in TODAY_RECOMMENDATIONS:
                add_recommendation(
                    item["home_team"],
                    item["away_team"],
                    item["time"],
                    item["pick"],
                    item["confidence"],
                    item["reasons"],
                    item["medal"],
                    connection=connection,
                )
        if connection.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO history(event_date, match_name, pick, result, success) VALUES (?, ?, ?, ?, ?)",
                [(item["date"], item["match"], item["pick"], item["result"], int(item["success"])) for item in HISTORY],
            )


def add_recommendation(
    home_team: str,
    away_team: str,
    match_time: str,
    pick: str,
    confidence: str,
    reasons: list[str],
    medal: str = "⭐",
    connection: sqlite3.Connection | None = None,
) -> int:
    owns_connection = connection is None
    database = connection or connect()
    cursor = database.execute(
        """
        INSERT INTO recommendations(
            recommendation_date, home_team, away_team, match_time, pick,
            confidence, medal, reasons_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (date.today().isoformat(), home_team, away_team, match_time, pick, confidence, medal, json.dumps(reasons, ensure_ascii=False)),
    )
    database.commit()
    if owns_connection:
        database.close()
    return int(cursor.lastrowid)


def get_today_recommendations(limit: int = 3) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, home_team, away_team, match_time, pick, confidence, medal, reasons_json
            FROM recommendations
            WHERE recommendation_date = ? AND active = 1
            ORDER BY id
            LIMIT ?
            """,
            (date.today().isoformat(), limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "time": row["match_time"],
            "pick": row["pick"],
            "confidence": row["confidence"],
            "medal": row["medal"],
            "reasons": json.loads(row["reasons_json"]),
        }
        for row in rows
    ]


def get_history() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT event_date, match_name, pick, result, success FROM history ORDER BY id DESC LIMIT 20"
        ).fetchall()
    return [
        {
            "date": row["event_date"],
            "match": row["match_name"],
            "pick": row["pick"],
            "result": row["result"],
            "success": bool(row["success"]),
        }
        for row in rows
    ]


def get_active_recommendations(limit: int = 50) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, recommendation_date, home_team, away_team, match_time, pick,
                   confidence, medal, reasons_json
            FROM recommendations
            WHERE active = 1
            ORDER BY recommendation_date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "date": row["recommendation_date"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "time": row["match_time"],
            "pick": row["pick"],
            "confidence": row["confidence"],
            "medal": row["medal"],
            "reasons": json.loads(row["reasons_json"]),
        }
        for row in rows
    ]


def finish_recommendation(recommendation_id: int, success: bool) -> bool:
    with connect() as connection:
        row = connection.execute(
            "SELECT home_team, away_team, pick FROM recommendations WHERE id = ? AND active = 1",
            (recommendation_id,),
        ).fetchone()
        if row is None:
            return False
        connection.execute(
            "INSERT INTO history(event_date, match_name, pick, result, success) VALUES (?, ?, ?, ?, ?)",
            (
                date.today().strftime("%d.%m.%Y"),
                f"{row['home_team']} מול {row['away_team']}",
                row["pick"],
                "הצליחה" if success else "לא הצליחה",
                int(success),
            ),
        )
        connection.execute("UPDATE recommendations SET active = 0 WHERE id = ?", (recommendation_id,))
    return True


def export_database() -> dict:
    return {
        "exported_at": date.today().isoformat(),
        "active_recommendations": get_active_recommendations(),
        "history": get_history(),
    }
