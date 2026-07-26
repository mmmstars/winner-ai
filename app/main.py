import hashlib
import hmac
import os
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import (
    add_recommendation,
    export_database,
    finish_recommendation,
    get_active_recommendations,
    get_history,
    get_today_recommendations,
    initialize_database,
)

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Winner AI", version="0.3.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
initialize_database()


def today_text() -> str:
    return date.today().strftime("%d.%m.%Y")


def admin_token() -> str:
    pin = os.getenv("ADMIN_PIN", "")
    return hmac.new(pin.encode(), b"winner-ai-admin-v1", hashlib.sha256).hexdigest() if pin else ""


def is_admin(request: Request) -> bool:
    token = request.cookies.get("winner_admin", "")
    expected = admin_token()
    return bool(expected) and hmac.compare_digest(token, expected)


async def read_form(request: Request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs((await request.body()).decode("utf-8")).items()}


def admin_context(request: Request, **extra: object) -> dict:
    authenticated = is_admin(request)
    return {
        "authenticated": authenticated,
        "enabled": bool(os.getenv("ADMIN_PIN")),
        "recommendations": get_active_recommendations() if authenticated else [],
        **extra,
    }


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
        context=admin_context(request, saved=request.query_params.get("saved") == "1"),
    )


@app.post("/admin/login")
async def admin_login(request: Request) -> HTMLResponse:
    form = await read_form(request)
    configured_pin = os.getenv("ADMIN_PIN")
    if not configured_pin or not hmac.compare_digest(form.get("pin", ""), configured_pin):
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context=admin_context(request, error="הקוד אינו נכון."),
            status_code=status.HTTP_403_FORBIDDEN,
        )
    response = RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        "winner_admin",
        admin_token(),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        max_age=60 * 60 * 8,
    )
    return response


@app.post("/admin/logout")
async def admin_logout() -> RedirectResponse:
    response = RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("winner_admin")
    return response


@app.post("/admin/recommendations", response_class=HTMLResponse)
async def create_recommendation(request: Request) -> HTMLResponse:
    if not is_admin(request):
        return HTMLResponse("אין הרשאה", status_code=status.HTTP_403_FORBIDDEN)
    form = await read_form(request)
    required = ("home_team", "away_team", "match_time", "pick", "confidence", "reason_1")
    if any(not form.get(field, "").strip() for field in required):
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context=admin_context(request, error="יש למלא את כל שדות החובה."),
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


@app.post("/admin/recommendations/{recommendation_id}/finish")
async def close_recommendation(recommendation_id: int, request: Request):
    if not is_admin(request):
        return HTMLResponse("אין הרשאה", status_code=status.HTTP_403_FORBIDDEN)
    form = await read_form(request)
    success = form.get("result") == "success"
    finish_recommendation(recommendation_id, success)
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/backup")
async def download_backup(request: Request) -> JSONResponse:
    if not is_admin(request):
        return JSONResponse({"error": "אין הרשאה"}, status_code=status.HTTP_403_FORBIDDEN)
    return JSONResponse(
        export_database(),
        headers={"Content-Disposition": f'attachment; filename="winner-ai-backup-{date.today().isoformat()}.json"'},
    )


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
