import sys
import unittest
from unittest.mock import MagicMock
from datetime import date, timedelta

# Create Mock classes that behave like NamedTuples / Dataclasses
class MockShift:
    def __init__(self, id, date, type, start_time, end_time, duration_hours, required_staff_count):
        self.id = id
        self.date = date
        self.type = type
        self.start_time = start_time
        self.end_time = end_time
        self.duration_hours = duration_hours
        self.required_staff_count = required_staff_count

class MockStaff:
    def __init__(self, id, status="Active"):
        self.id = id
        self.status = status

# Patch pydantic / ortools so import succeeds
sys.modules['pydantic'] = MagicMock()

ortools_mock = MagicMock()
sys.modules['ortools'] = ortools_mock
sys.modules['ortools.sat'] = MagicMock()
sys.modules['ortools.sat.python'] = MagicMock()
sys.modules['ortools.sat.python.cp_model'] = MagicMock()

# Import logic
from app.optimizer import RosterOptimizer

class TestRosterOptimizerFix(unittest.TestCase):
    def test_continuous_dates(self):
        # Create shifts with a gap day
        shifts = [
            MockShift(id="S1", date=date(2023, 10, 1), type="Day", start_time=800, end_time=1600, duration_hours=8.0, required_staff_count=1),
            MockShift(id="S2", date=date(2023, 10, 3), type="Day", start_time=800, end_time=1600, duration_hours=8.0, required_staff_count=1), # Gap on Oct 2
        ]
        staff = [MockStaff(id="Alice")]

        optimizer = RosterOptimizer(staff_list=staff, shifts=shifts)

        # In optimizer.__init__, assignments is initialized to {}.
        # For our mock testing, we need to populate self.assignments otherwise `self.model.Add(sum(...))` fails with KeyError
        for stf in staff:
            for shft in shifts:
                optimizer.assignments[(stf.id, shft.id)] = 1

        # Mock the CP Model Add
        optimizer.model = MagicMock()

        # Test consecutive days logic
        optimizer._apply_max_consecutive_days()

        # Test weekly hours logic
        optimizer._apply_max_weekly_hours()

        print("Test passed successfully without errors.")

if __name__ == "__main__":
    unittest.main()
