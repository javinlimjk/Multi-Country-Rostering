import sys
sys.path.append('.')

import subprocess
import json

script = """
import sys
import pydantic
from app.forecaster import StaffingForecaster

f = StaffingForecaster()
shift_inputs = [
    {"Name": "Morning", "Start Time": 800, "Duration": 8, "Staff Needed": 5}
]
res = f.calculate_needs_simulation(shift_inputs, days=2, country="SG", absence_buffer=0.15)
import json
print("JSON_RESULT:" + json.dumps(res))
"""

with open("temp_test.py", "w") as f:
    f.write(script)

# Run in an environment where dependencies are installed if possible?
# But pydantic might be missing. Wait, the previous test failed because mock cp_model Add failed.
# It seems ortools is the missing one that makes the Optimizer break since we mocked it.
