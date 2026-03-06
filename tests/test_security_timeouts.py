
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.modules['requests'] = MagicMock()

from app.demand_planner import FlightService

class TestSecurityTimeouts(unittest.TestCase):
    @patch('app.demand_planner.requests.get')
    def test_flight_service_timeout(self, mock_get):
        # Mocking the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        # Set API key to trigger real-ish path
        with patch.dict(os.environ, {"FLIGHT_API_KEY": "dummy_key"}):
            service = FlightService()
            service.get_flights("SIN", "2023-10-27")

            # Verify requests.get was called with timeout=10
            self.assertTrue(mock_get.called, "requests.get was not called")
            args, kwargs = mock_get.call_args
            self.assertEqual(kwargs.get('timeout'), 10, "FlightService.get_flights should call requests.get with timeout=10")

if __name__ == "__main__":
    unittest.main()
