
import unittest
from app.forecaster import StaffingForecaster
from app.models import Country

class TestForecaster(unittest.TestCase):
    def test_forecast_simulation(self):
        forecaster = StaffingForecaster()

        # Mock inputs: 2 Morning shifts per day for 7 days
        shift_inputs = [
            {"Name": "Morning", "Start Time": 800, "Duration": 8, "Staff Needed": 2}
        ]

        result = forecaster.calculate_needs_simulation(shift_inputs, days=7, country="SG", absence_buffer=0.15)

        # Expectations:
        # 2 staff per day needed.
        # Max concurrency = 2.
        # Total shifts = 14.
        # Max hours per person = 44.
        # Min staff by volume = (14 * 8) / 44 = 112 / 44 = 2.54 -> 3 staff needed by volume.
        # Min staff by concurrency = 2.
        # So optimizer should find ~3 staff as minimum feasible.
        # With buffer: 3 / 0.85 = 3.5 -> 4 staff recommended.

        print(f"Forecast Result: {result}")

        self.assertEqual(result['status'], 'OPTIMAL')
        self.assertGreaterEqual(result['min_staff'], 2)
        self.assertGreaterEqual(result['rec_staff'], result['min_staff'])
        self.assertTrue(len(result['logs']) > 0)

if __name__ == "__main__":
    unittest.main()
