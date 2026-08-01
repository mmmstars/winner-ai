"""Allow-list for free/open sources. Unknown sources never auto-fetch."""

from app.engine_models import SourcePolicy


SOURCES = {
    "official-israel-import": SourcePolicy(
        "official-israel-import", "ייבוא רשמי — ההתאחדות/מנהלת הליגות", 1.0, False,
        "https://www.football.org.il/", "קובץ שהמשתמש הוריד או הזין; אין סריקה אוטומטית.",
    ),
    "football-data.org": SourcePolicy(
        "football-data.org", "football-data.org", .92, True,
        "https://www.football-data.org/coverage", "שכבה חינמית עם מפתח ומגבלת קצב.",
    ),
    "openligadb": SourcePolicy(
        "openligadb", "OpenLigaDB", .88, True,
        "https://www.openligadb.de/", "API פתוח; נשמר מטמון מקומי.",
    ),
    "openfootball-import": SourcePolicy(
        "openfootball-import", "OpenFootball", .82, False,
        "https://github.com/openfootball", "ייבוא קובץ פתוח מקומי; ללא סריקת אתרים.",
    ),
    "football-data.co.uk": SourcePolicy("football-data.co.uk", "Football-Data.co.uk", .90, True, "https://www.football-data.co.uk/downloadm.php", "קובצי CSV היסטוריים; הורדה מרוכזת ארבע פעמים ביום לכל היותר."),
    "statsbomb-open": SourcePolicy("statsbomb-open", "StatsBomb Open Data", .94, True, "https://github.com/statsbomb/open-data", "נתוני מחקר פתוחים; יש להציג קרדיט ל־StatsBomb."),
    "thesportsdb": SourcePolicy("thesportsdb", "TheSportsDB", .76, True, "https://www.thesportsdb.com/docs_api_guide", "שכבה חינמית; עד 30 בקשות בדקה."),
    "open-meteo": SourcePolicy("open-meteo", "Open-Meteo", .86, True, "https://open-meteo.com/en/docs", "תחזית מזג אוויר, בשימוש לא מסחרי ועם קרדיט."),
    "manual": SourcePolicy("manual", "הזנה ידנית", .70, False, "", "הנתון מוצג כהזנה ידנית."),
    "public-israel-estimate": SourcePolicy(
        "public-israel-estimate", "לוח הדגמה ישראלי", .35, False, "",
        "נתון מובנה להדגמה בלבד; אינו לוח רשמי ואינו יחס שוק.",
    ),
}


def source_policy(key: str) -> SourcePolicy:
    return SOURCES.get(key, SourcePolicy(key, "מקור לא מוכר", 0.0, False, "", "המקור נחסם עד לבדיקה."))


def public_source_status() -> list[dict]:
    return [
        {
            "key": item.key,
            "name": item.label_he,
            "reliability": item.reliability,
            "automatic": item.automated_access,
            "notes": item.notes_he,
        }
        for item in SOURCES.values()
    ]
