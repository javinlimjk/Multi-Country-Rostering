
import unittest
from datetime import date, timedelta
from app.models import Staff, Shift, Country
from app.optimizer import RosterOptimizer

class TestRosterOptimizer(unittest.TestCase):
    def test_max_weekly_hours_constraint_with_float_duration(self):
        # 7 days of shifts to trigger _apply_max_weekly_hours
        start_date = date(2023, 10, 27)
        shifts = []

        for i in range(7):
            curr = start_date + timedelta(days=i)
            curr_str = curr.isoformat()
            shifts.append(Shift(
                id=f"S_{i}",
                date=curr_str,
                type="Day",
                start_time=800,
                end_time=1600,
                duration_hours=8.0, # FLOAT!
                required_staff_count=1
            ))

        staff_list = [Staff(id="Alice")]

        optimizer = RosterOptimizer(staff_list, shifts)

        # This should NOT crash
        try:
            optimizer.solve()
        except TypeError as e:
            self.fail(f"Optimizer crashed with TypeError: {e}")
        except Exception as e:
            # We don't care if it's infeasible or whatever, just no TypeError
            pass

if __name__ == "__main__":
    unittest.main()
