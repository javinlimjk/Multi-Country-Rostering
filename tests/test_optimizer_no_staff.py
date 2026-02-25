
import pytest
from app.models import Shift, Staff
from app.optimizer import RosterOptimizer
from datetime import date

def test_auto_generate_staff():
    # 1. Create shifts
    shifts = [
        Shift(
            id="S1", date="2024-01-01", type="Morning",
            start_time=800, end_time=1200, duration_hours=4, required_staff_count=1
        ),
        Shift(
            id="S2", date="2024-01-01", type="Afternoon",
            start_time=1300, end_time=1700, duration_hours=4, required_staff_count=1
        )
    ]

    # 2. Init Optimizer with empty staff
    opt = RosterOptimizer([], shifts)

    # 3. Check if staff were generated
    # Peak concurrency is 1. Buffer 1.5 * 1 + 2 = 3 (int(1.5)+2 = 1+2=3).
    assert len(opt.staff_list) == 3
    assert opt.staff_list[0].id.startswith("Open_Pos_")

def test_auto_generate_staff_overlap():
    # 1. Overlapping shifts
    shifts = [
        Shift(
            id="S1", date="2024-01-01", type="Morning",
            start_time=800, end_time=1200, duration_hours=4, required_staff_count=1
        ),
        Shift(
            id="S2", date="2024-01-01", type="Morning",
            start_time=800, end_time=1200, duration_hours=4, required_staff_count=1
        )
    ]
    # 2 shifts at same time. Max overlap 2.

    opt = RosterOptimizer([], shifts)

    # Max overlap 2.
    # 2 * 1.5 = 3.0 -> 3. 3 + 2 = 5.
    assert len(opt.staff_list) == 5

if __name__ == "__main__":
    test_auto_generate_staff()
    test_auto_generate_staff_overlap()
    print("Tests passed!")
