import sys
from unittest.mock import MagicMock

# Mock external dependencies that might not be installed
sys.modules['streamlit'] = MagicMock()
sys.modules['pandas'] = MagicMock()
sys.modules['plotly.express'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Setup a dummy return value so the module load works
st_mock = sys.modules['streamlit']
st_mock.selectbox.return_value = "Singapore"

from frontend.dashboard import highlight_shifts

def test_highlight_shifts_night():
    assert highlight_shifts('Night') == 'background-color: #4a148c; color: white'

def test_highlight_shifts_morning():
    assert highlight_shifts('Morning Ops') == 'background-color: #e65100; color: white'

def test_highlight_shifts_afternoon():
    assert highlight_shifts('Afternoon') == 'background-color: #01579b; color: white'

def test_highlight_shifts_off():
    assert highlight_shifts('Off') == 'background-color: #718096; color: white'

def test_highlight_shifts_mc():
    assert highlight_shifts('MC') == 'background-color: #C53030; color: white'

def test_highlight_shifts_leave():
    assert highlight_shifts('Leave') == 'background-color: #C53030; color: white'

def test_highlight_shifts_other():
    assert highlight_shifts('Unknown') == ''

def test_highlight_shifts_none():
    assert highlight_shifts(None) == ''

def test_highlight_shifts_int():
    # If a number is passed, it converts to string and returns '' since it's not in the list
    assert highlight_shifts(123) == ''
