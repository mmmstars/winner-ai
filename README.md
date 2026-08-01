# Winner AI

מערכת עברית לניתוח טופס Winner 16, יצירת מספר טפסים ומעקב ביצועים. הממשק הראשי הוא "גרסת אבא": טקסט גדול, ניגודיות גבוהה ומעט פעולות.

## כתובות

- גרסת Production: `https://winner-ai-production.up.railway.app/`
- יצירת טפסים: `/builder`
- ביצועים והיסטוריה: `/history`
- בדיקת תקינות: `/health`
- תיעוד API: `/docs`

## יכולות

- טבלת 16 משחקים בעברית.
- מנוע משולב: יחסי שוק, Elo ופואסון.
- יצירת עד 20 טפסים עם פיזור ומניעת כפילויות.
- Backtesting: דיוק, Brier score, Log Loss וכיול.
- למידת דירוגי קבוצות מתוצאות שהוזנו.
- סנכרון אוטומטי עם API-Football, football-data.org, OpenLigaDB ומקור ישראלי ציבורי.
- שמות וכינויים עבריים לקבוצות בישראל.
- בניית מחזור אוטומטי כאשר קיימים 16 משחקים עם יחסי 1/X/2.
- PWA, היסטוריה, גיבוי ומסך ניהול מוגן.

## משתני סביבה

העתק את `.env.example` והגדר לפחות:

- `API_FOOTBALL_KEY` — נתוני ישראל, משחקים ויחסים.
- `ADMIN_PIN` — קוד כניסה למסך הניהול.
- `WINNER_DB_PATH` — נתיב SQLite קבוע. ב־Railway יש לחבר Volume ל־`/data`.
- `BACKUP_DIR` — תיקיית גיבויים. ברירת המחדל היא `/data/backups`.

המשחקים הישראליים הציבוריים ויחסיהם אינם טופס Winner רשמי; כאשר אין יחסי שוק זמינים הם מסומנים ומחושבים כהערכה.

אין לשמור מפתחות בקוד או ב־GitHub.

## הרצה מקומית

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## בדיקות

```powershell
pytest -q
```

המערכת מספקת המלצות בלבד ואינה שולחת הימורים.
