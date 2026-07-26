import os
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import add_recommendation, get_history, get_today_recommendations, initialize_database

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Winner AI", version="0.2.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
initialize_database()


def today_text() -> str:
    return date.today().strftime("%d.%m.%Y")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"recommendations": get_today_recommendations(), "today": today_text()},
    )


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="history.html", context={"history": get_history()})


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"saved": request.query_params.get("saved") == "1", "enabled": bool(os.getenv("ADMIN_PIN"))},
    )


@app.post("/admin/recommendations", response_class=HTMLResponse)
async def create_recommendation(
    request: Request,
) -> HTMLResponse:
    form = {key: values[0] for key, values in parse_qs((await request.body()).decode("utf-8")).items()}
    pin = form.get("pin", "")
    configured_pin = os.getenv("ADMIN_PIN")
    if not configured_pin or pin != configured_pin:
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={"saved": False, "enabled": bool(configured_pin), "error": "הקוד אינו נכון."},
            status_code=status.HTTP_403_FORBIDDEN,
        )
    required = ("home_team", "away_team", "match_time", "pick", "confidence", "reason_1")
    if any(not form.get(field, "").strip() for field in required):
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={"saved": False, "enabled": True, "error": "יש למלא את כל שדות החובה."},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    reasons = [
        form.get(field, "").strip()
        for field in ("reason_1", "reason_2", "reason_3")
        if form.get(field, "").strip()
    ]
    add_recommendation(
        form["home_team"].strip(),
        form["away_team"].strip(),
        form["match_time"].strip(),
        form["pick"].strip(),
        form["confidence"].strip(),
        reasons,
    )
    return RedirectResponse("/admin?saved=1", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/api/recommendations/today")
async def today_recommendations() -> dict:
    recommendations = get_today_recommendations()
    return {"date": today_text(), "count": len(recommendations), "demo": True, "recommendations": recommendations}


@app.get("/api/history")
async def recommendation_history() -> dict:
    return {"demo": True, "history": get_history()}


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
