import sys
sys.path.append('.')

from unittest.mock import MagicMock
sys.modules['pandas'] = MagicMock()

import logging
logging.basicConfig(level=logging.INFO)

from app.forecaster import StaffingForecaster

if __name__ == "__main__":
    f = StaffingForecaster()
    shift_inputs = [
        {"Name": "Morning", "Start Time": 800, "Duration": 8.5, "Staff Needed": 5}
    ]
    res = f.calculate_needs_simulation(shift_inputs, days=2, country="SG", absence_buffer=0.15)
    print("RESULT:", res)
