
import pytest
from datetime import date, timedelta
from app.models import Shift, Staff
from app.optimizer import RosterOptimizer

def test_auto_staff_generation_volume():
    """
    Test that auto-generation creates enough staff based on total hours volume,
    even if peak concurrency is low.
    """
    start_date = date(2024, 1, 1)
    shifts = []

    # 7 days of 3 sequential shifts (8 hours each)
    # Total hours = 7 * 3 * 8 = 168 hours
    # Max overlap = 1 (since they are sequential)

    for i in range(7):
        current_date = (start_date + timedelta(days=i)).isoformat()
        # Morning 00:00 - 08:00
        shifts.append(Shift(
            id=f"M_{i}", date=current_date, type="M", start_time=0, end_time=800, duration_hours=8, required_staff_count=1
        ))
        # Afternoon 08:00 - 16:00
        shifts.append(Shift(
            id=f"A_{i}", date=current_date, type="A", start_time=800, end_time=1600, duration_hours=8, required_staff_count=1
        ))
        # Night 16:00 - 24:00
        shifts.append(Shift(
            id=f"N_{i}", date=current_date, type="N", start_time=1600, end_time=2400, duration_hours=8, required_staff_count=1
        ))

    # Rules: 44 hours max per week
    rules = {"max_weekly_hours": 44, "min_rest_hours": 10}

    # Initialize Optimizer with NO staff
    optimizer = RosterOptimizer([], shifts, rules)

    generated_staff = optimizer.staff_list
    print(f"Generated Staff Count: {len(generated_staff)}")

    # Calculation:
    # Total Hours: 168
    # Capacity per person: 44
    # Min Needed: 168 / 44 = 3.81
    # Old Logic (Concurrency): Max Overlap = 1 -> 1*1.5 + 2 = 3.5 -> 3 or 4 staff.
    # If 3 staff: 3 * 44 = 132 hours max. 168 needed. FAIL.
    # New Logic (Volume): 3.8 * 1.2 = 4.56 -> 5 + 1 buffer = 6 staff? Or int(4.5)+1 = 5.

    assert len(generated_staff) >= 4, f"Expected at least 4 staff, got {len(generated_staff)}"

    # Try to solve to ensure feasibility
    result = optimizer.solve()
    assert result is not None, "Optimization failed with generated staff"
    print("Optimization Successful")

if __name__ == "__main__":
    test_auto_staff_generation_volume()
