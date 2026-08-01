from datetime import datetime, timedelta, timezone
import pytest

from app.conflict_resolution import resolve_records
from app.engine_models import TeamSnapshot
from app.evaluation import safe_recalibration
from app.features import h2h_features, snapshot_features, table_position
from app.normalization import match_team, normalized_name
from app.prediction import GameInput, market_analysis
from app.source_adapters import parse_official_csv
from app.source_registry import source_policy


def test_normalization_is_safe_and_supports_aliases():
    assert normalized_name("Maccabi Haifa FC") == "maccabi haifa"
    aliases = {"Maccabi Haifa FC": "מכבי חיפה", "Hapoel Haifa": "הפועל חיפה"}
    assert match_team("Maccabi Haifa", aliases)[0] == "מכבי חיפה"
    assert match_team("Haifa", aliases)[0] is None


def test_conflict_resolution_prefers_reliable_source_and_audits_conflict():
    now = datetime.now(timezone.utc).isoformat()
    chosen, audit = resolve_records([
        {"source": "official-israel-import", "observed_at": now, "status": "finished", "home_score": 2},
        {"source": "manual", "observed_at": now, "status": "finished", "home_score": 1},
    ])
    assert chosen["home_score"] == 2
    assert next(item for item in audit if item["field"] == "home_score")["conflict"] is True
    assert source_policy("unknown").reliability == 0


def test_features_cover_form_splits_table_and_h2h():
    item = snapshot_features(TeamSnapshot(team="א", played=5, points=10, goals_for=8, goals_against=4, home_played=3, home_points=7, away_played=2, away_points=3, recent_points=[3, 1, 3, 0, 3]))
    assert item["form"] == pytest.approx(10 / 15, abs=.0001)
    assert item["attack"] == 1.6
    assert table_position({"א": 10, "ב": 8}, {"א": (8, 4), "ב": (7, 4)}, "א") == 1
    assert h2h_features([(2, 1), (0, 0)])["draw_rate"] == .5


def test_prediction_exposes_confidence_and_value():
    analysis = market_analysis(GameInput(number=1, home_team="א", away_team="ב", home_odds=3.2, draw_odds=3.1, away_odds=2.4, home_elo=1750, away_elo=1450, home_table_position=1, away_table_position=10))
    assert analysis["prediction"] in {"1", "X", "2"}
    assert 0 <= analysis["confidence"] <= 100
    assert set(analysis["value"]) == {"1", "X", "2"}


def test_prediction_changes_as_kickoff_approaches_and_reports_quality():
    common = dict(number=1, home_team="א", away_team="ב", home_odds=2.2, draw_odds=3.1,
                  away_odds=3.4, home_elo=1650, away_elo=1450, home_form=.8, away_form=.3,
                  history_matches=20, h2h_matches=5, odds_are_estimated=True)
    far = market_analysis(GameInput(**common, kickoff_at=datetime.now(timezone.utc) + timedelta(days=40)))
    near = market_analysis(GameInput(**common, kickoff_at=datetime.now(timezone.utc) + timedelta(hours=8)))
    assert far["model"] != near["model"]
    assert near["hours_to_kickoff"] < far["hours_to_kickoff"]
    assert near["data_quality"] > 0


def test_official_csv_adapter_and_guarded_recalibration():
    content = "external_id,competition,kickoff_at,home_team,away_team,status\n1,ISR,2026-08-10T18:00:00+03:00,מכבי חיפה,הפועל חיפה,scheduled\n"
    items = parse_official_csv(content)
    assert items[0]["source"] == "official-israel-import"
    result = safe_recalibration({"market": .45, "elo": .2, "goals": .2, "factors": .15}, {"market": .4, "elo": .2, "goals": .2, "factors": .2}, [], [])
    assert result["accepted"] is False
