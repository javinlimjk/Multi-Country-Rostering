
import unittest
from datetime import datetime, timedelta
from app.demand_planner import calculate_required_staff

class TestDemandPlanner(unittest.TestCase):
    def test_calculate_required_staff(self):
        # Mock flight data
        base_time = datetime(2023, 10, 27, 8, 0, 0) # 08:00

        # Case 1: Aligned task (09:30 Departure, 90m window: 08:00-09:30)
        flights_aligned = [{
            'flight_number': 'SQ100',
            'type': 'departure',
            'time': base_time + timedelta(minutes=90), # 09:30
            'aircraft': 'A320', # Narrow body
            'pax': 150
        }]

        demand_aligned = calculate_required_staff(flights_aligned)

        # Expect 9 staff (6 Ramp/Gate + 3 Check-in)
        # Check-in window: 2h before departure -> 07:30 to 09:30.
        # Ramp window: 90m before departure -> 08:00 to 09:30.

        # 07:30 bucket: Only Check-in (3)
        self.assertEqual(demand_aligned.get("07:30"), 3)

        # 08:00 bucket: Check-in (3) + Ramp (6) = 9
        self.assertEqual(demand_aligned.get("08:00"), 9)
        self.assertEqual(demand_aligned.get("08:30"), 9)
        self.assertEqual(demand_aligned.get("09:00"), 9)

        # 09:30 bucket: 0 (Ends exactly at 09:30)
        self.assertEqual(demand_aligned.get("09:30", 0), 0)


        # Case 2: Unaligned task (09:45 Departure, 90m window: 08:15-09:45)
        # Check-in window: 2h before -> 07:45 to 09:45.

        flights_unaligned = [{
            'flight_number': 'SQ101',
            'type': 'departure',
            'time': base_time + timedelta(minutes=105), # 09:45
            'aircraft': 'A320',
            'pax': 150
        }]

        demand_unaligned = calculate_required_staff(flights_unaligned)

        # 07:30 bucket (07:30-08:00): Overlaps with Checkin (07:45-08:00) -> 3
        self.assertEqual(demand_unaligned.get("07:30"), 3)

        # 08:00 bucket (08:00-08:30): Checkin (3) + Ramp (Start 08:15, so 08:15-08:30 overlap -> 6) = 9
        self.assertEqual(demand_unaligned.get("08:00"), 9)

        # 08:30 bucket: Both active = 9
        self.assertEqual(demand_unaligned.get("08:30"), 9)
        self.assertEqual(demand_unaligned.get("09:00"), 9)

        # 09:30 bucket (09:30-10:00): Both active until 09:45 -> 9
        self.assertEqual(demand_unaligned.get("09:30"), 9)

        # 10:00 bucket: 0
        self.assertEqual(demand_unaligned.get("10:00", 0), 0)

if __name__ == "__main__":
    unittest.main()
