
import unittest
import os
import sys

from unittest.mock import MagicMock

class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not hasattr(self, 'shifts'): self.shifts = []
        if not hasattr(self, 'month_year'): self.month_year = None
        if not hasattr(self, 'start_time'): self.start_time = None
        if not hasattr(self, 'duration_hours'): self.duration_hours = None

sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic'].BaseModel = MockBaseModel
sys.modules['pydantic'].Field = MagicMock()

# Set up PYTHONPATH equivalent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.state import RosterState, ShiftItem

class TestRosterStateMissingFields(unittest.TestCase):
    def test_missing_fields_all_missing(self):
        """Test missing_fields when all fields are missing"""
        state = RosterState(shifts=[], month_year=None)
        missing = state.missing_fields()
        self.assertIn("shift details (name, time, duration, staff count)", missing)
        self.assertIn("the month and year for the roster", missing)
        self.assertEqual(len(missing), 2)

    def test_missing_fields_only_shifts_missing(self):
        """Test missing_fields when only shifts are missing"""
        state = RosterState(shifts=[], month_year="October 2023")
        missing = state.missing_fields()
        self.assertIn("shift details (name, time, duration, staff count)", missing)
        self.assertNotIn("the month and year for the roster", missing)
        self.assertEqual(len(missing), 1)

    def test_missing_fields_only_month_year_missing(self):
        """Test missing_fields when only month_year is missing"""
        shift = ShiftItem(name="Morning", start_time=800, duration_hours=8, staff_needed=5)
        state = RosterState(shifts=[shift], month_year=None)
        missing = state.missing_fields()
        self.assertNotIn("shift details (name, time, duration, staff count)", missing)
        self.assertIn("the month and year for the roster", missing)
        self.assertEqual(len(missing), 1)

    def test_missing_fields_none_missing(self):
        """Test missing_fields when no fields are missing"""
        shift = ShiftItem(name="Morning", start_time=800, duration_hours=8, staff_needed=5)
        state = RosterState(shifts=[shift], month_year="October 2023")
        missing = state.missing_fields()
        self.assertEqual(len(missing), 0)

if __name__ == "__main__":
    unittest.main()
