from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_home_is_hebrew_dad_mode() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'dir="rtl"' in response.text
    assert "שלום אבא" in response.text
    assert "ההמלצות של היום" in response.text
    assert "נתוני הדגמה" in response.text


def test_home_shows_up_to_three_recommendations() -> None:
    response = client.get("/")

    assert "מכבי חיפה" in response.text
    assert "מכבי תל אביב" in response.text
    assert response.text.count('class="recommendation-card"') <= 3


def test_history_page() -> None:
    response = client.get("/history")

    assert response.status_code == 200
    assert "היסטוריה" in response.text
    assert "הצליחה" in response.text
    assert "לא הצליחה" in response.text


def test_today_api() -> None:
    response = client.get("/api/recommendations/today")
    payload = response.json()

    assert response.status_code == 200
    assert payload["demo"] is True
    assert payload["count"] == 2
    assert len(payload["recommendations"]) <= 3


def test_history_api() -> None:
    response = client.get("/api/history")
    payload = response.json()

    assert response.status_code == 200
    assert payload["demo"] is True
    assert len(payload["history"]) == 2


def test_installable_assets() -> None:
    manifest = client.get("/static/manifest.webmanifest")
    worker = client.get("/service-worker.js")
    icon = client.get("/static/icon.svg")

    assert manifest.status_code == 200
    assert worker.status_code == 200
    assert "winner-ai-v010" in worker.text
    assert icon.status_code == 200
