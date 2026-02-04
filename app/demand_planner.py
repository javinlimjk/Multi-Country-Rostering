
import requests
import os
from datetime import datetime, timedelta
from collections import defaultdict

# --- CONFIGURATION ---
STAFFING_CONFIG = {
    "narrow_body": {
        "codes": ["A319", "A320", "A321", "B737", "B738", "B739", "E190"],
        "ramp_agents": 4,
        "gate_agents": 2,
        "window_minutes": 90
    },
    "wide_body": {
        "codes": ["A330", "A350", "A380", "B747", "B777", "B787"],
        "ramp_agents": 10,
        "gate_agents": 5,
        "window_minutes": 120
    },
    "check_in": {
        "pax_per_agent": 40,
        "window_minutes": 120, # Assume check-in open 2h before
        "window_offset_minutes": -120 # Starts 2h before departure
    }
}

class FlightService:
    def __init__(self):
        self.api_key = os.getenv("FLIGHT_API_KEY")
        # Base URL for Aviationstack (example)
        self.base_url = "http://api.aviationstack.com/v1/flights"

    def get_flights(self, airport_code: str, date_str: str = None):
        """
        Fetches flights for a given airport and date.
        Returns a list of dicts:
        [{
            'flight_number': 'SQ123',
            'type': 'arrival'/'departure',
            'time': datetime,
            'aircraft': 'B777',
            'pax': 300 (estimated if not provided)
        }]
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        if not self.api_key:
            print("⚠️ No FLIGHT_API_KEY found. Returning mock data.")
            return self._get_mock_flights(date_str)

        try:
            params = {
                'access_key': self.api_key,
                'dep_iata': airport_code, # Departures
            }
            # Note: Aviationstack free tier doesn't support date filtering well on historical/future,
            # often just 'real-time'. We might need 'flight_date' param if supported.
            # For simplicity, we'll try to fetch and parse.

            # This is a simplified implementation. Real-world might need separate calls for arr/dep.
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            flights = []
            if 'data' in data:
                for f in data['data']:
                    # Extract relevant fields
                    f_date = f.get('flight_date')
                    if f_date != date_str: continue # Client-side filter if API doesn't support

                    dep_time = f.get('departure', {}).get('scheduled')
                    ac_iata = f.get('aircraft', {}).get('iata')

                    if dep_time:
                        flights.append({
                            'flight_number': f.get('flight', {}).get('iata', 'UNK'),
                            'type': 'departure',
                            'time': datetime.fromisoformat(dep_time),
                            'aircraft': ac_iata if ac_iata else 'A320', # Default to narrow
                            'pax': 180 # API might not give pax, assume avg
                        })
            return flights

        except Exception as e:
            print(f"Error fetching flights: {e}")
            return self._get_mock_flights(date_str)

    def _get_mock_flights(self, date_str):
        # Generate some dummy pattern
        base = datetime.strptime(date_str, "%Y-%m-%d")
        flights = []

        # Morning Rush
        for i in range(6, 10):
            flights.append({
                'flight_number': f'SQ{100+i}',
                'type': 'departure',
                'time': base.replace(hour=i, minute=0),
                'aircraft': 'A320',
                'pax': 150
            })

        # Heavy Widebody Noon
        flights.append({
            'flight_number': 'SQ222',
            'type': 'departure',
            'time': base.replace(hour=12, minute=30),
            'aircraft': 'A380',
            'pax': 450
        })

        # Evening Wave
        for i in range(18, 22):
             flights.append({
                'flight_number': f'SQ{300+i}',
                'type': 'departure',
                'time': base.replace(hour=i, minute=15),
                'aircraft': 'B777',
                'pax': 300
            })

        return flights

def _distribute_demand(buckets, start_time, end_time, count):
    """
    Distributes 'count' staff demand to all 30-minute buckets overlapping with [start_time, end_time).
    """
    if count <= 0 or start_time >= end_time:
        return

    # Helper to snap to previous 30-min mark
    def snap_to_bucket(t):
        remainder = t.minute % 30
        return t - timedelta(minutes=remainder, seconds=t.second, microseconds=t.microsecond)

    start_bucket = snap_to_bucket(start_time)
    # For end_time, we want the bucket that contains end_time - epsilon
    # If end_time is 09:30, it stops exactly at start of 09:30 bucket, so it shouldn't count for 09:30.
    # So we calculate bucket for (end_time - 1 microsecond)
    end_bucket = snap_to_bucket(end_time - timedelta(microseconds=1))

    # Iterate from start_bucket to end_bucket inclusive
    curr = start_bucket
    while curr <= end_bucket:
        if curr in buckets:
            buckets[curr] += count
        curr += timedelta(minutes=30)

def calculate_required_staff(flights):
    """
    Converts a list of flights into a time-series demand signal.
    Returns:
        dict: {
            "08:00": 15,
            "08:30": 18,
            ...
        }
        (30-minute intervals)
    """
    # Initialize 30-min buckets for the whole day
    # Keys are datetime objects for the specific date
    # But for the output, we might just want "HH:MM" string if it's single day,
    # or keep ISO strings.

    if not flights: return {}

    # Sort to find range (though we usually cover 00:00 to 23:59 of that day)
    base_date = flights[0]['time'].date()
    start_of_day = datetime.combine(base_date, datetime.min.time())

    # Create buckets for 24h
    buckets = {}
    for i in range(48): # 24 * 2
        t = start_of_day + timedelta(minutes=30*i)
        buckets[t] = 0

    for f in flights:
        f_time = f['time']
        ac_type = f['aircraft']
        pax = f['pax'] or 150

        # Determine Ratios
        is_wide = ac_type in STAFFING_CONFIG['wide_body']['codes'] or '380' in ac_type or '777' in ac_type
        rule = STAFFING_CONFIG['wide_body'] if is_wide else STAFFING_CONFIG['narrow_body']

        # 1. Ramp & Gate Demand
        # Window starts at flight time (or slightly before? Prompt says "for a 90-minute window")
        # Usually ground handling is [Arr - 45, Dep] or [Dep - 90, Dep].
        # Prompt implies "Require X agents... for a window". Let's assume window starts at f_time (Arrival) or ends at f_time (Departure).
        # "Returns arrivals and departures".
        # Let's simplify: Window centers on event time or starts 60 mins before.
        # Let's assume the window starts 'window_minutes' BEFORE departure (for prep).

        start_task = f_time - timedelta(minutes=rule['window_minutes'])
        end_task = f_time

        needed = rule['ramp_agents'] + rule['gate_agents']

        # Add to buckets
        # Quantize to 30 min
        _distribute_demand(buckets, start_task, end_task, needed)

        # 2. Check-in Demand (Departures only)
        if f['type'] == 'departure':
            ci_agents = pax // STAFFING_CONFIG['check_in']['pax_per_agent']
            ci_start = f_time + timedelta(minutes=STAFFING_CONFIG['check_in']['window_offset_minutes'])
            ci_end = ci_start + timedelta(minutes=STAFFING_CONFIG['check_in']['window_minutes'])

            _distribute_demand(buckets, ci_start, ci_end, ci_agents)

    # Format Output: "HH:MM" -> Count
    output = {}
    for t in sorted(buckets.keys()):
        key = t.strftime("%H:%M")
        output[key] = buckets[t]

    return output
