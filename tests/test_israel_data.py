from app.israel_data import public_israel_data


def test_public_israel_data_is_ready_for_main_screen():
    teams, matches = public_israel_data()
    assert len(teams) == 14
    assert len(matches) >= 16
    assert matches[0]["competition"] == "ISR-DEMO"
    assert "home_odds" not in matches[0]
    assert abs(sum(matches[0]["estimated_probabilities"].values()) - 1) < .001
    assert matches[0]["source"] == "public-israel-estimate"
