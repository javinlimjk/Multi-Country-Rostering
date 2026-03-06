import sys
from unittest.mock import MagicMock

class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

mock_pydantic = MagicMock()
mock_pydantic.BaseModel = MockBaseModel
sys.modules['pydantic'] = mock_pydantic

from app.state import RosterState, ShiftItem

if __name__ == "__main__":
    state = RosterState(shifts=[], month_year=None)
    missing = state.missing_fields()
    print("MISSING ALL:", missing)
    print("HASATTR SHIFTS:", hasattr(state, 'shifts'))
    print("HASATTR MONTH_YEAR:", hasattr(state, 'month_year'))
    print("SHIFTS:", getattr(state, 'shifts', 'NOT FOUND'))
    print("MONTH_YEAR:", getattr(state, 'month_year', 'NOT FOUND'))
