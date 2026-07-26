from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.0.3"}


def test_home_is_hebrew_rtl_and_contains_primary_action() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'lang="he" dir="rtl"' in response.text
    assert "שלום אבא" in response.text
    assert "ההמלצה של היום" in response.text
    assert "מכבי חיפה" in response.text


def test_home_contains_simple_explanation_and_match_time() -> None:
    response = client.get("/")
    assert "למה בחרנו?" in response.text
    assert "שעת המשחק" in response.text
    assert "אין ודאות בתוצאות ספורט" in response.text


def test_home_is_installable() -> None:
    response = client.get("/")
    assert 'rel="manifest"' in response.text
    assert "/static/manifest.webmanifest" in response.text
    assert 'navigator.serviceWorker.register("/service-worker.js")' in response.text


def test_manifest_and_service_worker_are_available() -> None:
    manifest = client.get("/static/manifest.webmanifest")
    service_worker = client.get("/service-worker.js")
    icon = client.get("/static/icon.svg")

    assert manifest.status_code == 200
    assert manifest.json()["display"] == "standalone"
    assert manifest.json()["dir"] == "rtl"
    assert service_worker.status_code == 200
    assert service_worker.headers["service-worker-allowed"] == "/"
    assert icon.status_code == 200
