import pytest

from app.coupon_import import parse_coupon


def test_parse_coupon_builds_16_games():
    text = "\n".join(f"בית {number} | חוץ {number}" for number in range(1, 17))
    games = parse_coupon(text)
    assert len(games) == 16
    assert games[0].number == 1
    assert games[-1].away_team == "חוץ 16"


def test_parse_coupon_requires_16_games():
    with pytest.raises(ValueError, match="16"):
        parse_coupon("מכבי חיפה | הפועל חיפה")
