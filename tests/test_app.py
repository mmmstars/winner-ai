import os
import tempfile
from pathlib import Path
from uuid import uuid4

os.environ["WINNER_DB_PATH"] = str(Path(tempfile.gettempdir()) / f"winner-test-{uuid4()}.db")
os.environ["ADMIN_PIN"] = "246810"

from fastapi.testclient import TestClient
from app.main import app
from app.providers import parse_api_football_fixtures, parse_football_data_matches, parse_football_data_teams
from app.sync_service import configured_competitions
from app.elo import elo_probabilities, update_elo
from app.poisson import poisson_probabilities
from app.ticket_optimizer import distance


client = TestClient(app)


def sample_games() -> list[dict]:
    return [{"number": n, "home_team": f"בית {n}", "away_team": f"חוץ {n}", "home_odds": 2.1, "draw_odds": 3.2, "away_odds": 3.1} for n in range(1, 17)]


def test_health_and_hebrew_home():
    assert client.get("/health").json() == {"status": "ok", "version": "1.0.0"}
    page = client.get("/")
    assert page.status_code == 200
    assert 'dir="rtl"' in page.text
    assert "ההמלצות של היום" in page.text
    assert "dad-row" in page.text
    assert client.get("/builder").status_code == 200


def test_generate_settle_and_history():
    response = client.post("/api/tickets", json={"games": sample_games(), "ticket_count": 3, "strategy": "מאוזן"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["tickets"]) == 3
    assert all(len(ticket["picks"]) == 16 for ticket in data["tickets"])
    results = [pick["selection"] for pick in data["tickets"][0]["picks"]]
    settled = client.post(f"/api/runs/{data['run_id']}/settle", json={"results": results})
    assert settled.status_code == 200
    assert settled.json()["best_score"] == 16
    assert client.get("/api/ticket-history").json()[0]["best_score"] == 16
    learning = client.get("/api/learning").json()
    assert learning["matches"] >= 16
    assert learning["correct"] >= 16
    assert learning["ratings"]


def test_rejects_incomplete_coupon():
    response = client.post("/api/tickets", json={"games": sample_games()[:-1], "ticket_count": 1, "strategy": "בטוח"})
    assert response.status_code == 422


def test_market_margin_and_fair_probabilities():
    game = sample_games()[0]
    response = client.post("/api/market-analysis", json=game)
    assert response.status_code == 200
    data = response.json()
    assert data["bookmaker_margin"] > 0
    assert abs(sum(data["fair"].values()) - 1) < 0.001
    assert data["method"] == "simple_normalization"
    assert abs(sum(data["power"].values()) - 1) < 0.001


def test_create_complete_round_and_retrieve_it():
    response = client.post(
        "/api/rounds",
        json={"name": "מחזור בדיקה", "closes_at": "2026-08-08T12:00:00+03:00", "games": sample_games()},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "מחזור בדיקה"
    assert len(data["games"]) == 16
    assert data["games"][0]["bookmaker_margin"] > 0
    assert client.get(f"/api/rounds/{data['id']}").json()["games"] == data["games"]
    teams = client.get("/api/teams?q=בית").json()
    assert len(teams) == 16
    assert teams[0]["name_he"].startswith("בית")


def test_admin_security_and_assets():
    assert client.get("/admin/backup").status_code == 403
    login = client.post("/admin/login", data={"pin": "246810"}, follow_redirects=False)
    assert login.status_code == 303
    assert client.get("/static/manifest.webmanifest").status_code == 200
    assert client.get("/service-worker.js").status_code == 200


def test_provider_team_normalization():
    teams = parse_football_data_teams({"teams": [{"id": 5, "name": "FC Example", "shortName": "Example", "tla": "EXA"}]})
    assert teams == [{"external_id": "5", "name_he": "Example", "aliases": ["FC Example", "Example", "EXA"]}]


def test_provider_match_normalization():
    payload = {"matches": [{"id": 9, "utcDate": "2026-08-02T18:00:00Z", "status": "SCHEDULED", "homeTeam": {"id": 1, "name": "Home FC", "shortName": "Home"}, "awayTeam": {"id": 2, "name": "Away FC", "shortName": "Away"}}]}
    matches = parse_football_data_matches(payload, "PL")
    assert matches[0]["home_team"] == "Home"
    assert matches[0]["away_team"] == "Away"
    assert matches[0]["competition"] == "PL"


def test_sync_status_and_security():
    status = client.get("/api/sync/status")
    assert status.status_code == 200
    assert "PL" in status.json()["competitions"]
    assert configured_competitions()
    client.post("/admin/logout")
    assert client.post("/api/sync/all").status_code == 403


def test_api_football_israel_fixture_normalization():
    payload = {"response": [{"fixture": {"id": 77, "date": "2026-08-09T18:00:00+00:00", "status": {"short": "NS"}}, "teams": {"home": {"id": 10, "name": "Maccabi Haifa"}, "away": {"id": 20, "name": "Hapoel Beer Sheva"}}}]}
    teams, matches = parse_api_football_fixtures(payload, "383")
    assert len(teams) == 2
    assert matches[0]["home_team"] == "Maccabi Haifa"
    assert matches[0]["away_team"] == "Hapoel Beer Sheva"


def test_elo_and_poisson_models():
    stronger = elo_probabilities(1700, 1450)
    assert stronger["1"] > stronger["2"]
    new_home, new_away = update_elo(1500, 1500, "1", 2)
    assert new_home > 1500 and new_away < 1500
    goals = poisson_probabilities(2.0, 0.8, 0.9, 1.6)
    assert goals["1"] > goals["2"]
    assert abs(sum(goals.values()) - 1) < 0.001


def test_market_analysis_contains_blended_model():
    response = client.post("/api/market-analysis", json=sample_games()[0])
    assert response.status_code == 200
    assert abs(sum(response.json()["model"].values()) - 1) < 0.001


def test_backtest_metrics():
    items = [
        {"probabilities": {"1": 0.7, "X": 0.2, "2": 0.1}, "result": "1"},
        {"probabilities": {"1": 0.2, "X": 0.3, "2": 0.5}, "result": "X"},
    ]
    response = client.post("/api/backtest", json={"items": items})
    assert response.status_code == 200
    data = response.json()
    assert data["matches"] == 2
    assert data["accuracy"] == 0.5
    assert data["brier_score"] > 0
    assert data["log_loss"] > 0


def test_ticket_optimizer_creates_diverse_unique_tickets():
    response = client.post("/api/tickets", json={"games": sample_games(), "ticket_count": 5, "strategy": "נועז"})
    assert response.status_code == 200
    signatures = [tuple(pick["selection"] for pick in ticket["picks"]) for ticket in response.json()["tickets"]]
    assert len(signatures) == len(set(signatures)) == 5
    assert all(distance(signatures[0], signature) >= 1 for signature in signatures[1:])
