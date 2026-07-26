from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Winner AI", version="0.0.3")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

MOCK_RECOMMENDATION = {
    "home_team": "מכבי חיפה",
    "away_team": "הפועל באר שבע",
    "time": "20:30",
    "pick": "ניצחון מכבי חיפה",
    "confidence": "גבוהה",
    "reasons": [
        "מכבי חיפה משחקת בבית.",
        "הקבוצה נמצאת בכושר טוב.",
        "ההרכב שלה כמעט מלא.",
    ],
}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    today = date.today().strftime("%d.%m.%Y")
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"recommendation": MOCK_RECOMMENDATION, "today": today},
    )


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    return FileResponse(
        BASE_DIR / "static" / "service-worker.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
