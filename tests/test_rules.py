import pytest
from app.rules import get_rules_for_country
from app.optimizer import validate_roster_logic

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

from datetime import date

def test_validate_roster_logic_max_daily_hours():
    shift_definitions = [
        {'Name': 'LongShift', 'Start Time': 800, 'Duration': 13, 'Staff Needed': 1}
    ]
    rules = {
        'max_daily_hours': 12,
        'max_weekly_hours': 44,
        'max_consecutive_days': 6,
        'min_rest_hours': 10
    }
    assignments = [
        {'staff_id': 'S1', 'date': date(2023, 10, 1), 'shift': 'LongShift'}
    ]

    errors = validate_roster_logic(assignments, shift_definitions, rules)
    daily_errors = [e for e in errors if e['type'] == 'Daily Hours Violation']
    assert len(daily_errors) == 1
    assert "Worked 13.0h (Max 12h)" in daily_errors[0]['msg']

def test_validate_roster_logic_max_weekly_hours():
    shift_definitions = [
        {'Name': 'Normal', 'Start Time': 800, 'Duration': 8, 'Staff Needed': 1}
    ]
    rules = {
        'max_daily_hours': 12,
        'max_weekly_hours': 40,
        'max_consecutive_days': 6,
        'min_rest_hours': 10
    }
    assignments = [
        {'staff_id': 'S1', 'date': date(2023, 10, 1), 'shift': 'Normal'},
        {'staff_id': 'S1', 'date': date(2023, 10, 2), 'shift': 'Normal'},
        {'staff_id': 'S1', 'date': date(2023, 10, 3), 'shift': 'Normal'},
        {'staff_id': 'S1', 'date': date(2023, 10, 4), 'shift': 'Normal'},
        {'staff_id': 'S1', 'date': date(2023, 10, 5), 'shift': 'Normal'},
        {'staff_id': 'S1', 'date': date(2023, 10, 6), 'shift': 'Normal'}, # 6 * 8 = 48 hours
    ]

    errors = validate_roster_logic(assignments, shift_definitions, rules)
    weekly_errors = [e for e in errors if e['type'] == 'Weekly Hours Violation']
    assert len(weekly_errors) > 0
    assert "Worked 48.0h (Max 40h)" in weekly_errors[0]['msg']

def test_validate_roster_logic_max_consecutive_days():
    shift_definitions = [
        {'Name': 'Short', 'Start Time': 800, 'Duration': 4, 'Staff Needed': 1}
    ]
    rules = {
        'max_daily_hours': 12,
        'max_weekly_hours': 44,
        'max_consecutive_days': 3,
        'min_rest_hours': 10
    }
    assignments = [
        {'staff_id': 'S1', 'date': date(2023, 10, 1), 'shift': 'Short'},
        {'staff_id': 'S1', 'date': date(2023, 10, 2), 'shift': 'Short'},
        {'staff_id': 'S1', 'date': date(2023, 10, 3), 'shift': 'Short'},
        {'staff_id': 'S1', 'date': date(2023, 10, 4), 'shift': 'Short'}, # 4 days in a row
    ]

    errors = validate_roster_logic(assignments, shift_definitions, rules)
    consec_errors = [e for e in errors if e['type'] == 'Consecutive Days Violation']
    assert len(consec_errors) == 1
    assert "worked 4 days ending on 2023-10-04 (Max 3)" in consec_errors[0]['msg']
