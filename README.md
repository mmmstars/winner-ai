# Winner AI — Sprint 1

אפליקציית FastAPI מינימלית בעברית, עם תצוגה פשוטה ונגישה.

## הרצה מקומית

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

האפליקציה זמינה ב־`http://127.0.0.1:8000` ובדיקת התקינות ב־`/health`.

## בדיקות

```powershell
pytest
```
