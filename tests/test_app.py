import os
import tempfile
from pathlib import Path
from uuid import uuid4

os.environ["WINNER_DB_PATH"] = str(Path(tempfile.gettempdir()) / f"winner-test-{uuid4()}.db")
os.environ["ADMIN_PIN"] = "246810"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.0"}


def test_home_is_hebrew_dad_mode() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'dir="rtl"' in response.text
    assert "שלום אבא" in response.text
    assert "ההמלצות של היום" in response.text


def test_home_shows_up_to_three_recommendations() -> None:
    response = client.get("/")
    assert "מכבי חיפה" in response.text
    assert "מכבי תל אביב" in response.text
    assert response.text.count('class="recommendation"') <= 3


def test_history_page() -> None:
    response = client.get("/history")
    assert response.status_code == 200
    assert "היסטוריה" in response.text
    assert "הצליחה" in response.text
    assert "לא הצליחה" in response.text


def test_admin_page_is_separate_from_dad_mode() -> None:
    response = client.get("/admin")
    assert response.status_code == 200
    assert "הוספת המלצה" in response.text
    assert "/admin" not in client.get("/").text


def test_admin_rejects_wrong_pin() -> None:
    response = client.post(
        "/admin/recommendations",
        data={
            "pin": "000000",
            "home_team": "קבוצה א",
            "away_team": "קבוצה ב",
            "match_time": "18:00",
            "pick": "ניצחון קבוצה א",
            "confidence": "גבוהה",
            "reason_1": "משחק בית.",
        },
    )
    assert response.status_code == 403


def test_admin_can_add_recommendation() -> None:
    response = client.post(
        "/admin/recommendations",
        data={
            "pin": "246810",
            "home_team": "קבוצה חדשה",
            "away_team": "יריבה חדשה",
            "match_time": "21:00",
            "pick": "ניצחון קבוצה חדשה",
            "confidence": "גבוהה",
            "reason_1": "כושר טוב.",
            "reason_2": "משחק בית.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin?saved=1"
    payload = client.get("/api/recommendations/today").json()
    assert payload["count"] == 3
    assert any(item["home_team"] == "קבוצה חדשה" for item in payload["recommendations"])


def test_data_apis() -> None:
    today = client.get("/api/recommendations/today")
    history = client.get("/api/history")
    assert today.status_code == 200
    assert len(today.json()["recommendations"]) <= 3
    assert history.status_code == 200
    assert len(history.json()["history"]) == 2


def test_installable_assets() -> None:
    assert client.get("/static/manifest.webmanifest").status_code == 200
    assert client.get("/service-worker.js").status_code == 200
    assert client.get("/static/icon.svg").status_code == 200
