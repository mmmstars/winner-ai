import os
import tempfile
from pathlib import Path
from uuid import uuid4

os.environ["WINNER_DB_PATH"] = str(Path(tempfile.gettempdir()) / f"winner-test-{uuid4()}.db")
os.environ["ADMIN_PIN"] = "246810"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def login() -> None:
    response = client.post("/admin/login", data={"pin": "246810"}, follow_redirects=False)
    assert response.status_code == 303


def logout() -> None:
    client.post("/admin/logout")


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok", "version": "0.4.0"}


def test_dad_mode_and_history() -> None:
    home = client.get("/")
    history = client.get("/history")
    assert home.status_code == 200
    assert 'dir="rtl"' in home.text
    assert "המלצות היום" in home.text
    assert "ניצחון לקבוצת הבית" in home.text
    assert "ניצחון לקבוצת החוץ" in home.text
    assert ">1<" in home.text.replace(" ", "").replace("\n", "")
    assert ">X<" in home.text.replace(" ", "").replace("\n", "")
    assert ">2<" in home.text.replace(" ", "").replace("\n", "")
    assert "מומלץ" in home.text
    assert "למה?" in home.text
    assert "/admin" not in home.text
    assert history.status_code == 200
    assert "היסטוריה" in history.text


def test_admin_requires_login() -> None:
    logout()
    page = client.get("/admin")
    assert "קוד מנהל" in page.text
    assert "הוספת המלצה" not in page.text
    assert client.get("/admin/backup").status_code == 403


def test_admin_rejects_wrong_pin() -> None:
    response = client.post("/admin/login", data={"pin": "000000"})
    assert response.status_code == 403
    assert "הקוד אינו נכון" in response.text


def test_admin_login_and_add_recommendation() -> None:
    login()
    page = client.get("/admin")
    assert "הוספת המלצה" in page.text
    response = client.post(
        "/admin/recommendations",
        data={
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
    payload = client.get("/api/recommendations/today").json()
    assert payload["count"] == 3
    assert any(item["home_team"] == "קבוצה חדשה" for item in payload["recommendations"])


def test_finish_recommendation_moves_it_to_history() -> None:
    login()
    recommendations = client.get("/api/recommendations/today").json()["recommendations"]
    target = next(item for item in recommendations if item["home_team"] == "קבוצה חדשה")
    response = client.post(
        f"/admin/recommendations/{target['id']}/finish",
        data={"result": "success"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert all(item["id"] != target["id"] for item in client.get("/api/recommendations/today").json()["recommendations"])
    assert any(item["match"].startswith("קבוצה חדשה") for item in client.get("/api/history").json()["history"])


def test_backup_download() -> None:
    login()
    response = client.get("/admin/backup")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "active_recommendations" in response.json()
    assert "history" in response.json()


def test_installable_assets() -> None:
    assert client.get("/static/manifest.webmanifest").status_code == 200
    worker = client.get("/service-worker.js")
    assert worker.status_code == 200
    assert "winner-ai-v041" in worker.text
    assert client.get("/static/icon.svg").status_code == 200
