import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from app.data import HISTORY, TODAY_RECOMMENDATIONS
from app.elo import update_elo


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
            CREATE TABLE IF NOT EXISTS ticket_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ticket_count INTEGER NOT NULL,
                strategy TEXT NOT NULL,
                best_score INTEGER
            );
            CREATE TABLE IF NOT EXISTS ticket_picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                ticket_number INTEGER NOT NULL,
                game_number INTEGER NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                selection TEXT NOT NULL,
                confidence REAL NOT NULL,
                actual_result TEXT
            );
            CREATE TABLE IF NOT EXISTS toto_rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                closes_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'draft'
            );
            CREATE TABLE IF NOT EXISTS fixtures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL,
                game_number INTEGER NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                UNIQUE(round_id, game_number)
            );
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id INTEGER NOT NULL,
                captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                home_odds REAL NOT NULL,
                draw_odds REAL NOT NULL,
                away_odds REAL NOT NULL,
                source TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                model_version TEXT NOT NULL,
                home_probability REAL NOT NULL,
                draw_probability REAL NOT NULL,
                away_probability REAL NOT NULL,
                bookmaker_margin REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL UNIQUE,
                name_he TEXT NOT NULL,
                provider TEXT,
                external_id TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS team_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                alias TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS external_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                competition TEXT NOT NULL,
                kickoff_at TEXT NOT NULL,
                status TEXT NOT NULL,
                home_team_id INTEGER NOT NULL,
                away_team_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, external_id)
            );
            CREATE TABLE IF NOT EXISTS team_ratings (
                team_name TEXT PRIMARY KEY,
                elo REAL NOT NULL DEFAULT 1500,
                matches INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS learning_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                game_number INTEGER NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                predicted_result TEXT NOT NULL,
                actual_result TEXT NOT NULL,
                confidence REAL NOT NULL,
                success INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(run_id, game_number)
            );
            CREATE TABLE IF NOT EXISTS external_odds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                external_match_id TEXT NOT NULL,
                captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                home_odds REAL NOT NULL,
                draw_odds REAL NOT NULL,
                away_odds REAL NOT NULL,
                source TEXT NOT NULL,
                UNIQUE(provider, external_match_id)
            );
            CREATE TABLE IF NOT EXISTS team_metrics (
                provider TEXT NOT NULL,
                external_team_id TEXT NOT NULL,
                form REAL NOT NULL,
                goals_for REAL NOT NULL,
                goals_against REAL NOT NULL,
                matches INTEGER NOT NULL DEFAULT 0,
                captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(provider, external_team_id)
            );
            CREATE TABLE IF NOT EXISTS fixture_absences (
                provider TEXT NOT NULL,
                external_match_id TEXT NOT NULL,
                external_team_id TEXT NOT NULL,
                missing INTEGER NOT NULL DEFAULT 0,
                captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(provider, external_match_id, external_team_id)
            );
            """
        )
        _ensure_column(connection, "fixtures", "kickoff_at", "TEXT")
        _ensure_column(connection, "fixtures", "provider", "TEXT NOT NULL DEFAULT 'manual'")
        _ensure_column(connection, "fixtures", "external_match_id", "TEXT")
        _ensure_column(connection, "external_matches", "home_score", "INTEGER")
        _ensure_column(connection, "external_matches", "away_score", "INTEGER")
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


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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


def get_today_recommendations(limit: int = 16) -> list[dict]:
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


def save_ticket_run(games: list, tickets: list[dict], strategy: str) -> int:
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO ticket_runs(ticket_count, strategy) VALUES (?, ?)",
            (len(tickets), strategy),
        )
        run_id = int(cursor.lastrowid)
        by_number = {game.number: game for game in games}
        for ticket in tickets:
            for pick in ticket["picks"]:
                game = by_number[pick["game_number"]]
                connection.execute(
                    """INSERT INTO ticket_picks(
                       run_id,ticket_number,game_number,home_team,away_team,selection,confidence
                       ) VALUES (?,?,?,?,?,?,?)""",
                    (run_id, ticket["number"], game.number, game.home_team,
                     game.away_team, pick["selection"], pick["confidence"]),
                )
    return run_id


def settle_ticket_run(run_id: int, results: list[str]) -> int | None:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id,ticket_number,game_number,home_team,away_team,selection,confidence FROM ticket_picks WHERE run_id=?",
            (run_id,),
        ).fetchall()
        if not rows:
            return None
        scores: dict[int, int] = {}
        for row in rows:
            actual = results[row["game_number"] - 1]
            connection.execute("UPDATE ticket_picks SET actual_result=? WHERE id=?", (actual, row["id"]))
            scores[row["ticket_number"]] = scores.get(row["ticket_number"], 0) + int(row["selection"] == actual)
        best = max(scores.values())
        connection.execute("UPDATE ticket_runs SET best_score=? WHERE id=?", (best, run_id))
        first_by_game = {}
        for row in rows:
            first_by_game.setdefault(row["game_number"], row)
        for game_number, row in first_by_game.items():
            actual = results[game_number - 1]
            _learn_result(connection, run_id, row, actual)
    return best


def settle_ready_runs() -> int:
    with connect() as connection:
        run_ids = [row[0] for row in connection.execute("SELECT id FROM ticket_runs WHERE best_score IS NULL")]
    settled = 0
    for run_id in run_ids:
        with connect() as connection:
            games = connection.execute(
                """SELECT game_number,home_team,away_team FROM ticket_picks
                   WHERE run_id=? AND ticket_number=1 ORDER BY game_number""", (run_id,)
            ).fetchall()
            results = []
            for game in games:
                score = connection.execute(
                    """SELECT m.home_score,m.away_score FROM external_matches m
                       JOIN teams h ON h.id=m.home_team_id JOIN teams a ON a.id=m.away_team_id
                       WHERE h.name_he=? AND a.name_he=? AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
                       ORDER BY m.kickoff_at DESC LIMIT 1""",
                    (game["home_team"], game["away_team"]),
                ).fetchone()
                if not score:
                    break
                results.append("1" if score["home_score"] > score["away_score"] else "2" if score["home_score"] < score["away_score"] else "X")
        if len(results) == 16 and settle_ticket_run(run_id, results) is not None:
            settled += 1
    return settled


def _learn_result(connection: sqlite3.Connection, run_id: int, row: sqlite3.Row, actual: str) -> None:
    home_rating = _rating(connection, row["home_team"])
    away_rating = _rating(connection, row["away_team"])
    new_home, new_away = update_elo(home_rating, away_rating, actual, 1)
    for name, rating in ((row["home_team"], new_home), (row["away_team"], new_away)):
        connection.execute(
            """INSERT INTO team_ratings(team_name,elo,matches) VALUES(?,?,1)
               ON CONFLICT(team_name) DO UPDATE SET elo=excluded.elo,matches=team_ratings.matches+1,updated_at=CURRENT_TIMESTAMP""",
            (name, rating),
        )
    connection.execute(
        """INSERT OR IGNORE INTO learning_events(
           run_id,game_number,home_team,away_team,predicted_result,actual_result,confidence,success
           ) VALUES(?,?,?,?,?,?,?,?)""",
        (run_id, row["game_number"], row["home_team"], row["away_team"], row["selection"], actual, row["confidence"], int(row["selection"] == actual)),
    )


def _rating(connection: sqlite3.Connection, team_name: str) -> float:
    row = connection.execute("SELECT elo FROM team_ratings WHERE team_name=?", (team_name,)).fetchone()
    return float(row["elo"]) if row else 1500.0


def get_learning_summary() -> dict:
    with connect() as connection:
        totals = connection.execute(
            """SELECT COUNT(*) matches,COALESCE(SUM(success),0) correct,
               COALESCE(ROUND(AVG(success)*100,2),0) accuracy FROM learning_events"""
        ).fetchone()
        ratings = connection.execute(
            "SELECT team_name,ROUND(elo,2) elo,matches FROM team_ratings ORDER BY matches DESC,elo DESC LIMIT 50"
        ).fetchall()
    result = dict(totals)
    result["ratings"] = [dict(row) for row in ratings]
    return result


def get_ticket_history() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id,created_at,ticket_count,strategy,best_score FROM ticket_runs ORDER BY id DESC LIMIT 50"
        ).fetchall()
    return [dict(row) for row in rows]


def get_ticket_statistics() -> dict:
    with connect() as connection:
        row = connection.execute(
            """SELECT COUNT(*) runs, COUNT(best_score) settled,
               COALESCE(ROUND(AVG(best_score),2),0) average,
               COALESCE(MAX(best_score),0) best FROM ticket_runs"""
        ).fetchone()
    return dict(row)


def create_round(name: str, closes_at: str, games: list, analyses: list[dict]) -> int:
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO toto_rounds(name, closes_at) VALUES (?, ?)", (name, closes_at)
        )
        round_id = int(cursor.lastrowid)
        for game, analysis in zip(games, analyses, strict=True):
            _upsert_team(connection, game.home_team)
            _upsert_team(connection, game.away_team)
            fixture = connection.execute(
                """INSERT INTO fixtures(round_id,game_number,home_team,away_team,kickoff_at,provider,external_match_id)
                   VALUES(?,?,?,?,?,?,?)""",
                (round_id, game.number, game.home_team, game.away_team,
                 game.kickoff_at.isoformat() if game.kickoff_at else None,
                 game.provider, game.external_match_id),
            )
            fixture_id = int(fixture.lastrowid)
            connection.execute(
                """INSERT INTO odds_snapshots(
                   fixture_id,home_odds,draw_odds,away_odds,source
                   ) VALUES(?,?,?,?,?)""",
                (fixture_id, game.home_odds, game.draw_odds, game.away_odds, "manual"),
            )
            model = analysis["model"]
            connection.execute(
                """INSERT INTO predictions(
                   fixture_id,model_version,home_probability,draw_probability,
                   away_probability,bookmaker_margin) VALUES(?,?,?,?,?,?)""",
                (fixture_id, "market-elo-poisson-v2", model["1"], model["X"], model["2"], analysis["bookmaker_margin"]),
            )
    return round_id


def _upsert_team(connection: sqlite3.Connection, name: str, provider: str | None = None, external_id: str | None = None) -> int:
    canonical = " ".join(name.casefold().split())
    connection.execute(
        """INSERT INTO teams(canonical_name,name_he,provider,external_id) VALUES(?,?,?,?)
           ON CONFLICT(canonical_name) DO UPDATE SET
           name_he=excluded.name_he,
           provider=COALESCE(excluded.provider,teams.provider),
           external_id=COALESCE(excluded.external_id,teams.external_id),
           updated_at=CURRENT_TIMESTAMP""",
        (canonical, name.strip(), provider, external_id),
    )
    team_id = connection.execute("SELECT id FROM teams WHERE canonical_name=?", (canonical,)).fetchone()[0]
    connection.execute(
        "INSERT OR IGNORE INTO team_aliases(team_id,alias) VALUES(?,?)", (team_id, name.strip())
    )
    return int(team_id)


def import_teams(items: list[dict], provider: str) -> int:
    with connect() as connection:
        for item in items:
            team_id = _upsert_team(connection, item["name_he"], provider, str(item.get("external_id", "")))
            for alias in item.get("aliases", []):
                connection.execute(
                    "INSERT OR IGNORE INTO team_aliases(team_id,alias) VALUES(?,?)",
                    (team_id, alias.strip()),
                )
    return len(items)


def list_teams(query: str = "", limit: int = 100) -> list[dict]:
    pattern = f"%{query.strip()}%"
    with connect() as connection:
        rows = connection.execute(
            """SELECT DISTINCT t.id,t.name_he,t.canonical_name,t.provider,t.external_id
               FROM teams t LEFT JOIN team_aliases a ON a.team_id=t.id
               WHERE t.name_he LIKE ? OR t.canonical_name LIKE ? OR a.alias LIKE ?
               ORDER BY t.name_he LIMIT ?""",
            (pattern, pattern.casefold(), pattern, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def import_matches(items: list[dict], provider: str) -> int:
    with connect() as connection:
        for item in items:
            home_id = _upsert_team(connection, item["home_team"], provider, item["home_external_id"])
            away_id = _upsert_team(connection, item["away_team"], provider, item["away_external_id"])
            connection.execute(
                """INSERT INTO external_matches(provider,external_id,competition,kickoff_at,status,home_team_id,away_team_id,home_score,away_score)
                   VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(provider,external_id) DO UPDATE SET
                   competition=excluded.competition,kickoff_at=excluded.kickoff_at,status=excluded.status,
                   home_team_id=excluded.home_team_id,away_team_id=excluded.away_team_id,
                   home_score=excluded.home_score,away_score=excluded.away_score,updated_at=CURRENT_TIMESTAMP""",
                (provider, item["external_id"], item["competition"], item["kickoff_at"], item["status"], home_id, away_id, item.get("home_score"), item.get("away_score")),
            )
    return len(items)


def import_external_odds(items: list[dict], provider: str) -> int:
    with connect() as connection:
        for item in items:
            connection.execute(
                """INSERT INTO external_odds(provider,external_match_id,home_odds,draw_odds,away_odds,source)
                   VALUES(?,?,?,?,?,?) ON CONFLICT(provider,external_match_id) DO UPDATE SET
                   captured_at=CURRENT_TIMESTAMP,home_odds=excluded.home_odds,draw_odds=excluded.draw_odds,
                   away_odds=excluded.away_odds,source=excluded.source""",
                (provider, item["external_id"], item["home_odds"], item["draw_odds"], item["away_odds"], item["source"]),
            )
    return len(items)


def import_team_metrics(items: list[dict], provider: str) -> int:
    with connect() as connection:
        for item in items:
            connection.execute(
                """INSERT INTO team_metrics(provider,external_team_id,form,goals_for,goals_against,matches)
                   VALUES(?,?,?,?,?,?) ON CONFLICT(provider,external_team_id) DO UPDATE SET
                   form=excluded.form,goals_for=excluded.goals_for,goals_against=excluded.goals_against,
                   matches=excluded.matches,captured_at=CURRENT_TIMESTAMP""",
                (provider, item["external_id"], item["form"], item["goals_for"], item["goals_against"], item["matches"]),
            )
    return len(items)


def import_fixture_absences(fixture_id: str, counts: dict[str, int], provider: str) -> int:
    with connect() as connection:
        for team_id, missing in counts.items():
            connection.execute(
                """INSERT INTO fixture_absences(provider,external_match_id,external_team_id,missing)
                   VALUES(?,?,?,?) ON CONFLICT(provider,external_match_id,external_team_id) DO UPDATE SET
                   missing=excluded.missing,captured_at=CURRENT_TIMESTAMP""",
                (provider, fixture_id, team_id, missing),
            )
    return len(counts)


def upcoming_matches(limit: int = 100) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT m.id,m.provider,m.external_id,m.competition,m.kickoff_at,m.status,
               h.name_he home_team,a.name_he away_team,h.external_id home_external_id,a.external_id away_external_id,
               o.home_odds,o.draw_odds,o.away_odds,
               COALESCE(hm.form,0.5) home_form,COALESCE(am.form,0.5) away_form,
               COALESCE(hm.goals_for,1.4) home_goals_for,COALESCE(hm.goals_against,1.2) home_goals_against,
               COALESCE(am.goals_for,1.2) away_goals_for,COALESCE(am.goals_against,1.4) away_goals_against,
               COALESCE(ha.missing,0) home_missing,COALESCE(aa.missing,0) away_missing
               FROM external_matches m JOIN teams h ON h.id=m.home_team_id JOIN teams a ON a.id=m.away_team_id
               LEFT JOIN external_odds o ON o.provider=m.provider AND o.external_match_id=m.external_id
               LEFT JOIN team_metrics hm ON hm.provider=m.provider AND hm.external_team_id=h.external_id
               LEFT JOIN team_metrics am ON am.provider=m.provider AND am.external_team_id=a.external_id
               LEFT JOIN fixture_absences ha ON ha.provider=m.provider AND ha.external_match_id=m.external_id AND ha.external_team_id=h.external_id
               LEFT JOIN fixture_absences aa ON aa.provider=m.provider AND aa.external_match_id=m.external_id AND aa.external_team_id=a.external_id
               WHERE m.status IN ('scheduled','ns','tbd') ORDER BY m.kickoff_at LIMIT ?""", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def round_id_by_name(name: str) -> int | None:
    with connect() as connection:
        row = connection.execute("SELECT id FROM toto_rounds WHERE name=? ORDER BY id DESC LIMIT 1", (name,)).fetchone()
    return int(row["id"]) if row else None


def delete_round(round_id: int) -> None:
    with connect() as connection:
        fixture_ids = [row[0] for row in connection.execute("SELECT id FROM fixtures WHERE round_id=?", (round_id,))]
        for fixture_id in fixture_ids:
            connection.execute("DELETE FROM odds_snapshots WHERE fixture_id=?", (fixture_id,))
            connection.execute("DELETE FROM predictions WHERE fixture_id=?", (fixture_id,))
        connection.execute("DELETE FROM fixtures WHERE round_id=?", (round_id,))
        connection.execute("DELETE FROM toto_rounds WHERE id=?", (round_id,))


def get_round(round_id: int) -> dict | None:
    with connect() as connection:
        round_row = connection.execute(
            "SELECT id,name,closes_at,created_at,status FROM toto_rounds WHERE id=?", (round_id,)
        ).fetchone()
        if round_row is None:
            return None
        rows = connection.execute(
            """SELECT f.game_number,f.home_team,f.away_team,f.kickoff_at,f.provider,f.external_match_id,
               o.home_odds,o.draw_odds,o.away_odds,
               p.home_probability,p.draw_probability,p.away_probability,p.bookmaker_margin
               FROM fixtures f JOIN odds_snapshots o ON o.fixture_id=f.id
               JOIN predictions p ON p.fixture_id=f.id
               WHERE f.round_id=? ORDER BY f.game_number""",
            (round_id,),
        ).fetchall()
    result = dict(round_row)
    result["games"] = [dict(row) for row in rows]
    return result


def latest_round() -> dict | None:
    with connect() as connection:
        row = connection.execute("SELECT id FROM toto_rounds ORDER BY id DESC LIMIT 1").fetchone()
    return get_round(int(row["id"])) if row else None


def latest_round_recommendations() -> list[dict]:
    with connect() as connection:
        latest = connection.execute("SELECT id FROM toto_rounds ORDER BY id DESC LIMIT 1").fetchone()
        if latest is None:
            return []
        rows = connection.execute(
            """SELECT f.game_number,f.home_team,f.away_team,f.kickoff_at,f.provider,
               p.home_probability,p.draw_probability,p.away_probability,p.bookmaker_margin
               FROM fixtures f JOIN predictions p ON p.fixture_id=f.id
               WHERE f.round_id=? ORDER BY f.game_number""",
            (latest["id"],),
        ).fetchall()
    items = []
    for row in rows:
        chances = {"1": row["home_probability"], "X": row["draw_probability"], "2": row["away_probability"]}
        selection = max(chances, key=chances.get)
        if abs(chances["1"] - chances["2"]) < 0.085 and chances["X"] >= 0.26:
            selection = "X"
        kickoff = "טרם נקבע"
        if row["kickoff_at"]:
            value = datetime.fromisoformat(row["kickoff_at"].replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Jerusalem"))
            kickoff = value.strftime("%d.%m · %H:%M")
        items.append({
            "home_team": row["home_team"], "away_team": row["away_team"], "time": kickoff,
            "provider": row["provider"],
            "selection": selection,
            "confidence": f"{round(chances[selection] * 100)}%",
            "reasons": [
                f"הסתברות המודל הגבוהה ביותר: {round(chances[selection] * 100)}%.",
                "התחזית משולבת ותתעדכן אוטומטית כשיתקבלו נתוני שוק נוספים.",
            ],
        })
    return items
