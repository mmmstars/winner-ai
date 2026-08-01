from datetime import datetime, timedelta, timezone


SOURCE = "https://sports.walla.co.il/league/2913?r=1"
STRENGTH = {
    "הפועל באר שבע": 1.00, "מכבי תל אביב": .96, "בית״ר ירושלים": .91,
    "מכבי חיפה": .88, "הפועל תל אביב": .77, "מכבי נתניה": .72,
    "בני סכנין": .64, "הפועל חיפה": .62, "הפועל ירושלים": .60,
    "עירוני קריית שמונה": .58, "מכבי פתח תקוה": .57,
    "הפועל פתח תקוה": .54, "עירוני טבריה": .52, "הפועל רמת גן": .49,
}

ROUNDS = [
    ("2026-08-22T17:00", [("מכבי פתח תקוה", "עירוני קריית שמונה"), ("עירוני טבריה", "הפועל פתח תקוה"), ("הפועל ירושלים", "מכבי תל אביב"), ("מכבי חיפה", "הפועל רמת גן"), ("הפועל באר שבע", "הפועל חיפה"), ("מכבי נתניה", "בני סכנין"), ("הפועל תל אביב", "בית״ר ירושלים")]),
    ("2026-08-29T20:00", [("בני סכנין", "מכבי פתח תקוה"), ("בית״ר ירושלים", "מכבי נתניה"), ("הפועל חיפה", "הפועל תל אביב"), ("הפועל רמת גן", "הפועל באר שבע"), ("מכבי תל אביב", "מכבי חיפה"), ("הפועל פתח תקוה", "הפועל ירושלים"), ("עירוני קריית שמונה", "עירוני טבריה")]),
    ("2026-09-05T17:00", [("מכבי פתח תקוה", "עירוני טבריה"), ("הפועל ירושלים", "עירוני קריית שמונה"), ("מכבי חיפה", "הפועל פתח תקוה"), ("הפועל באר שבע", "מכבי תל אביב"), ("הפועל תל אביב", "הפועל רמת גן"), ("מכבי נתניה", "הפועל חיפה"), ("בני סכנין", "בית״ר ירושלים")]),
]


def public_israel_data() -> tuple[list[dict], list[dict]]:
    teams = sorted({team for _, games in ROUNDS for game in games for team in game})
    team_items = [{"external_id": index, "name_he": name, "aliases": []} for index, name in enumerate(teams, 1)]
    matches = []
    for round_number, (kickoff, games) in enumerate(ROUNDS, 1):
        when = datetime.fromisoformat(kickoff).replace(tzinfo=timezone(timedelta(hours=3))).isoformat()
        for game_number, (home, away) in enumerate(games, 1):
            gap = STRENGTH.get(home, .6) + .08 - STRENGTH.get(away, .6)
            home_p = max(.22, min(.62, .40 + gap * .45))
            draw_p = .28 if abs(gap) < .18 else .25
            away_p = 1 - home_p - draw_p
            matches.append({"external_id": f"IL-2026-{round_number}-{game_number}", "competition": "ISR-WINNER", "kickoff_at": when, "status": "scheduled", "home_external_id": str(teams.index(home) + 1), "away_external_id": str(teams.index(away) + 1), "home_team": home, "away_team": away, "home_odds": round(1 / home_p, 3), "draw_odds": round(1 / draw_p, 3), "away_odds": round(1 / away_p, 3), "source": SOURCE})
    return team_items, matches
