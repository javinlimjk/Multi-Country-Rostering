def get_rules_for_country(country_code: str):
    """
    Returns a dictionary of constraints based on the country code.
    """
    code = str(country_code).upper()
    
    # Singapore Defaults
    if "SINGAPORE" in code or code == "SG":
        return {
            "max_weekly_hours": 44,
            "max_consecutive_days": 6,
            "min_rest_hours": 10,
            "max_daily_hours": 12
        }
    # Malaysia Defaults
    elif "MALAYSIA" in code or code == "MY":
        return {
            "max_weekly_hours": 48,
            "max_consecutive_days": 6,
            "min_rest_hours": 11,
            "max_daily_hours": 12
        }
    # Saudi Arabia Defaults
    elif "SAUDI" in code or code == "SA":
        return {
            "max_weekly_hours": 48,
            "max_consecutive_days": 6,
            "min_rest_hours": 12,
            "max_daily_hours": 10
        }
    # Fallback
    else:
        return {
            "max_weekly_hours": 44,
            "max_consecutive_days": 6,
            "min_rest_hours": 10,
            "max_daily_hours": 12
        }