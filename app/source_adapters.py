"""Adapters for user-supplied official exports and open datasets.

No adapter scrapes HTML. Network adapters live in providers.py and are allow-listed.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from app.normalization import normalized_name


REQUIRED_FIELDS = {"external_id", "competition", "kickoff_at", "home_team", "away_team"}


def parse_official_csv(content: str, source: str = "official-israel-import") -> list[dict]:
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
    if missing:
        raise ValueError("חסרות עמודות חובה: " + ", ".join(sorted(missing)))
    rows = []
    for number, item in enumerate(reader, start=2):
        try:
            kickoff = datetime.fromisoformat(item["kickoff_at"].replace("Z", "+00:00")).isoformat()
        except (TypeError, ValueError) as error:
            raise ValueError(f"תאריך לא תקין בשורה {number}") from error
        home, away = item["home_team"].strip(), item["away_team"].strip()
        if not home or not away or normalized_name(home) == normalized_name(away):
            raise ValueError(f"קבוצות לא תקינות בשורה {number}")
        row = {
            "external_id": item["external_id"].strip(), "competition": item["competition"].strip(),
            "kickoff_at": kickoff, "status": (item.get("status") or "scheduled").strip().lower(),
            "home_external_id": (item.get("home_external_id") or home).strip(),
            "away_external_id": (item.get("away_external_id") or away).strip(),
            "home_team": home, "away_team": away, "source": source,
        }
        for field in ("home_score", "away_score"):
            if item.get(field, "").strip():
                row[field] = int(item[field])
        rows.append(row)
    return rows


def parse_openfootball_json(content: str) -> list[dict]:
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError("קובץ OpenFootball חייב להכיל רשימת משחקים")
    return parse_official_csv(_json_to_csv(payload), "openfootball-import")


def _json_to_csv(items: list[dict]) -> str:
    if not items:
        return "external_id,competition,kickoff_at,home_team,away_team\n"
    fields = sorted(set().union(*(item.keys() for item in items)))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(items)
    return output.getvalue()

