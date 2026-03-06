
import sys
import unittest
from unittest.mock import MagicMock

# Create mock BaseModel for offline test execution
class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
mock_pydantic = MagicMock()
mock_pydantic.BaseModel = MockBaseModel
sys.modules['pydantic'] = mock_pydantic
import os
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
