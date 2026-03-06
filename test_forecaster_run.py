import sys
from unittest.mock import MagicMock
sys.modules['pandas'] = MagicMock()
sys.modules['ortools'] = MagicMock()
sys.modules['ortools.sat'] = MagicMock()
sys.modules['ortools.sat.python'] = MagicMock()
sys.modules['ortools.sat.python.cp_model'] = MagicMock()

class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

mock_pydantic = MagicMock()
mock_pydantic.BaseModel = MockBaseModel
sys.modules['pydantic'] = mock_pydantic

from app.forecaster import StaffingForecaster
from datetime import date

if __name__ == "__main__":
    f = StaffingForecaster()
    shift_inputs = [
        {"Name": "Morning", "Start Time": 800, "Duration": 8.5, "Staff Needed": 5}
    ]
    shifts = f._generate_dummy_shifts(shift_inputs, days=2)

    # Assertions
    assert len(shifts) == 10, f"Expected 10 shifts, got {len(shifts)}"
    assert shifts[0].duration_hours == 8.5, f"Expected float 8.5 duration, got {shifts[0].duration_hours}"
    assert isinstance(shifts[0].date, date), f"Expected date object, got {type(shifts[0].date)}"
    print("SUCCESS: Forecaster generates correct shifts!")
