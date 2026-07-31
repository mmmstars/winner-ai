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
    get_ticket_history,
    get_ticket_statistics,
    save_ticket_run,
    settle_ticket_run,
    create_round,
    get_round,
    import_teams,
    list_teams,
    latest_round_recommendations,
    import_matches,
    upcoming_matches,
)
from app.prediction import GameInput, GenerateRequest, RoundRequest, SettleRequest, TeamImportRequest, generate, market_analysis, power_probabilities
from app.providers import football_data_matches, football_data_teams

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Winner AI", version="1.0.0")
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


def recommendations_for_coupon() -> list[dict]:
    round_items = latest_round_recommendations()
    if round_items:
        return round_items
    items = []
    for recommendation in get_today_recommendations():
        item = dict(recommendation)
        pick = recommendation["pick"]
        if recommendation["home_team"] in pick:
            item["selection"] = "1"
        elif recommendation["away_team"] in pick:
            item["selection"] = "2"
        else:
            item["selection"] = "X"
        items.append(item)
    while len(items) < 16:
        items.append(
            {
                "home_team": "ממתין למשחק",
                "away_team": "יתעדכן אוטומטית",
                "time": "--:--",
                "selection": "",
                "reasons": ["המשחק וההמלצה יופיעו לאחר עדכון המחזור."],
            }
        )
    return items[:16]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    recommendations = recommendations_for_coupon()
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"recommendations": recommendations, "today": today_text(), "has_round": bool(latest_round_recommendations())},
    )


@app.get("/builder", response_class=HTMLResponse)
async def builder(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="builder.html",
        context={"today": today_text()},
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


@app.post("/api/tickets")
async def create_tickets(payload: GenerateRequest) -> dict:
    provisional = generate(payload, seed=0)
    run_id = save_ticket_run(payload.games, provisional, payload.strategy)
    tickets = generate(payload, seed=run_id)
    if run_id != 0:
        with __import__("app.database", fromlist=["connect"]).connect() as connection:
            connection.execute("DELETE FROM ticket_picks WHERE run_id=?", (run_id,))
            by_number = {game.number: game for game in payload.games}
            for ticket in tickets:
                for pick in ticket["picks"]:
                    game = by_number[pick["game_number"]]
                    connection.execute("INSERT INTO ticket_picks(run_id,ticket_number,game_number,home_team,away_team,selection,confidence) VALUES(?,?,?,?,?,?,?)", (run_id,ticket["number"],game.number,game.home_team,game.away_team,pick["selection"],pick["confidence"]))
    return {"run_id": run_id, "tickets": tickets}


@app.post("/api/market-analysis")
async def analyze_market(game: GameInput) -> dict:
    analysis = market_analysis(game)
    analysis["power"] = power_probabilities(game)
    return analysis


@app.post("/api/rounds")
async def new_round(payload: RoundRequest) -> dict:
    analyses = [market_analysis(game) for game in payload.games]
    round_id = create_round(payload.name, payload.closes_at.isoformat(), payload.games, analyses)
    return get_round(round_id)


@app.get("/api/rounds/{round_id}")
async def round_details(round_id: int) -> JSONResponse:
    item = get_round(round_id)
    if item is None:
        return JSONResponse({"error": "המחזור לא נמצא"}, status_code=404)
    return JSONResponse(item)


@app.get("/api/teams")
async def teams(q: str = "") -> list[dict]:
    return list_teams(q)


@app.post("/api/teams/import")
async def teams_import(payload: TeamImportRequest, request: Request) -> JSONResponse:
    if not is_admin(request):
        return JSONResponse({"error": "אין הרשאה"}, status_code=403)
    count = import_teams([team.model_dump() for team in payload.teams], payload.provider)
    return JSONResponse({"imported": count})


@app.post("/api/teams/sync/{competition}")
async def teams_sync(competition: str, request: Request) -> JSONResponse:
    if not is_admin(request):
        return JSONResponse({"error": "אין הרשאה"}, status_code=403)
    try:
        items = football_data_teams(competition)
    except RuntimeError as error:
        return JSONResponse({"error": str(error)}, status_code=503)
    count = import_teams(items, "football-data.org")
    return JSONResponse({"competition": competition.upper(), "imported": count})


@app.post("/api/matches/sync/{competition}")
async def matches_sync(competition: str, request: Request) -> JSONResponse:
    if not is_admin(request):
        return JSONResponse({"error": "אין הרשאה"}, status_code=403)
    try:
        items = football_data_matches(competition)
    except RuntimeError as error:
        return JSONResponse({"error": str(error)}, status_code=503)
    count = import_matches(items, "football-data.org")
    return JSONResponse({"competition": competition.upper(), "imported": count})


@app.get("/api/matches/upcoming")
async def matches_upcoming() -> list[dict]:
    return upcoming_matches()


@app.post("/api/runs/{run_id}/settle")
async def settle_tickets(run_id: int, payload: SettleRequest) -> JSONResponse:
    score = settle_ticket_run(run_id, payload.results)
    if score is None:
        return JSONResponse({"error": "ההרצה לא נמצאה"}, status_code=404)
    return JSONResponse({"best_score": score})


@app.get("/api/ticket-history")
async def ticket_history() -> list[dict]:
    return get_ticket_history()


@app.get("/api/statistics")
async def statistics() -> dict:
    return get_ticket_statistics()


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    return FileResponse(
        BASE_DIR / "static" / "service-worker.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}
