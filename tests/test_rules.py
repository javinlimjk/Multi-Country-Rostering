import pytest
from app.rules import get_rules_for_country

@pytest.mark.parametrize("country_code, expected", [
    # Singapore
    ("Singapore", {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),
    ("SG", {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),
    ("singapore", {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),
    ("sg", {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),

    # Malaysia
    ("Malaysia", {"max_weekly_hours": 48, "max_consecutive_days": 6, "min_rest_hours": 11, "max_daily_hours": 12}),
    ("MY", {"max_weekly_hours": 48, "max_consecutive_days": 6, "min_rest_hours": 11, "max_daily_hours": 12}),
    ("malaysia", {"max_weekly_hours": 48, "max_consecutive_days": 6, "min_rest_hours": 11, "max_daily_hours": 12}),
    ("my", {"max_weekly_hours": 48, "max_consecutive_days": 6, "min_rest_hours": 11, "max_daily_hours": 12}),

    # Saudi Arabia
    ("Saudi Arabia", {"max_weekly_hours": 48, "max_consecutive_days": 6, "min_rest_hours": 12, "max_daily_hours": 10}),
    ("SA", {"max_weekly_hours": 48, "max_consecutive_days": 6, "min_rest_hours": 12, "max_daily_hours": 10}),
    ("saudi", {"max_weekly_hours": 48, "max_consecutive_days": 6, "min_rest_hours": 12, "max_daily_hours": 10}),
    ("sa", {"max_weekly_hours": 48, "max_consecutive_days": 6, "min_rest_hours": 12, "max_daily_hours": 10}),

    # Fallback
    ("USA", {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),
    ("Unknown", {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),
    ("", {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),
    (123, {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),
    (None, {"max_weekly_hours": 44, "max_consecutive_days": 6, "min_rest_hours": 10, "max_daily_hours": 12}),
])
def test_get_rules_for_country(country_code, expected):
    assert get_rules_for_country(country_code) == expected
