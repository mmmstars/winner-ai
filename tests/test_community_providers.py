import json

from app import community_providers as providers


def test_football_data_uk_parses_results_and_closing_odds(monkeypatch):
    csv_data = "Date,HomeTeam,AwayTeam,FTHG,FTAG,AvgCH,AvgCD,AvgCA\n01/08/2026,Arsenal,Chelsea,2,1,2.10,3.40,3.60\n"
    monkeypatch.setattr(providers, "_read", lambda url: csv_data.encode())
    teams, matches, odds = providers.football_data_uk("2526", ["E0"])
    assert len(teams) == 2
    assert matches[0]["status"] == "finished"
    assert odds[0]["home_odds"] == 2.1
    assert odds[0]["source"] == "football-data.co.uk-csv"


def test_statsbomb_and_thesportsdb_normalize(monkeypatch):
    statsbomb = [{"match_id": 9, "match_date": "2024-01-01", "kick_off": "18:00:00", "home_team": {"home_team_id": 1, "home_team_name": "Home"}, "away_team": {"away_team_id": 2, "away_team_name": "Away"}, "home_score": 1, "away_score": 0}]
    monkeypatch.setattr(providers, "_read", lambda url: json.dumps(statsbomb).encode())
    teams, matches = providers.statsbomb_matches([(1, 2)])
    assert len(teams) == 2 and matches[0]["competition"] == "SB-1"

    sportsdb = {"events": [{"idEvent": "10", "dateEvent": "2026-08-02", "strTime": "20:00:00", "strHomeTeam": "Home", "strAwayTeam": "Away", "idHomeTeam": "1", "idAwayTeam": "2", "intHomeScore": None, "intAwayScore": None}]}
    monkeypatch.setattr(providers, "_read", lambda url: json.dumps(sportsdb).encode())
    _, matches = providers.thesportsdb_league_events(["4328"], "2026-2027")
    assert matches[0]["status"] == "scheduled"


def test_open_meteo_selects_nearest_hour(monkeypatch):
    payload = {"hourly": {"time": ["2026-08-02T19:00", "2026-08-02T20:00"], "temperature_2m": [28, 27], "precipitation": [0, 2], "wind_speed_10m": [10, 12]}}
    monkeypatch.setattr(providers, "_read", lambda url: json.dumps(payload).encode())
    weather = providers.open_meteo_weather(32.1, 34.8, "2026-08-02T20:05:00Z")
    assert weather["temperature"] == 27
    assert weather["precipitation"] == 2
