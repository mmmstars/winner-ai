from app.israel_data import public_israel_data


def test_public_israel_data_is_ready_for_main_screen():
    teams, matches = public_israel_data()
    assert len(teams) == 14
    assert len(matches) >= 16
    assert matches[0]["competition"] == "ISR-WINNER"
    assert matches[0]["home_odds"] > 1
