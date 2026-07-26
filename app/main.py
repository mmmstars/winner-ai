from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.data import HISTORY, TODAY_RECOMMENDATIONS

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Winner AI", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def today_text() -> str:
    return date.today().strftime("%d.%m.%Y")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="home.html",
        context={"recommendations": TODAY_RECOMMENDATIONS[:3], "today": today_text()},
    )


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="history.html", context={"history": HISTORY})


@app.get("/api/recommendations/today")
async def today_recommendations() -> dict:
    return {"date": today_text(), "count": len(TODAY_RECOMMENDATIONS[:3]), "demo": True, "recommendations": TODAY_RECOMMENDATIONS[:3]}


@app.get("/api/history")
async def recommendation_history() -> dict:
    return {"demo": True, "history": HISTORY}


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "service-worker.js", media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
