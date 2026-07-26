from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Winner AI", version="0.0.1")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

MOCK_RECOMMENDATION = {
    "home_team": "מכבי חיפה",
    "away_team": "הפועל באר שבע",
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
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"recommendation": MOCK_RECOMMENDATION},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
