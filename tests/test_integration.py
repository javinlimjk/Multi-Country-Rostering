
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import date

# Import the app (this will trigger startup events)
# We need to mock ComplianceEngine if laws dir is missing to avoid startup noise/errors
# but app.main handles missing dir gracefully.
from app.main import app

class TestSystemIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_forecast_endpoint(self):
        """Test /forecast calculation"""
        payload = {
            "shift_inputs": [
                {"Name": "Morning", "Start Time": 800, "Duration": 8, "Staff Needed": 5}
            ],
            "days": 7,
            "country": "SG",
            "buffer": 0.15
        }
        response = self.client.post("/forecast", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("min_staff", data)
        self.assertIn("rec_staff", data)
        self.assertGreaterEqual(data["rec_staff"], data["min_staff"])
        self.assertEqual(data["status"], "OPTIMAL")

    def test_optimize_endpoint_float_duration(self):
        """Test /optimize with float duration (Regression test for crash)"""
        staff_data = [
            {"id": "S1", "name": "Alice", "role": "Driver", "country": "SG"},
            {"id": "S2", "name": "Bob", "role": "Loader", "country": "SG"}
        ]

        # Shift with float duration (e.g. 8.5 hours)
        shifts_data = [
            {
                "id": "Shift_0",
                "date": date.today().isoformat(),
                "type": "Day",
                "start_time": 800,
                "end_time": 1630,
                "duration_hours": 8.5, # FLOAT
                "required_staff_count": 1
            }
        ]

        payload = {
            "staff": staff_data,
            "shifts": shifts_data,
            "country": "SG"
        }

        response = self.client.post("/optimize", json=payload)

        # Expect 200 OK or 400 Infeasible (if staff too few)
        # But NOT 500 Server Error (crash)

        # Here we have 2 staff and 1 shift requiring 1 person. Should be feasible.
        if response.status_code == 400:
             # Infeasible might happen due to rules/constraints, but let's check detail
             print(f"Optimize failed (expected feasibility): {response.text}")

        self.assertNotEqual(response.status_code, 500, "Server crashed with 500!")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("assignments", data)
        self.assertIn("metrics", data)
        # Check if success key exists, OR check status string.
        # App/optimizer.py line 76 returns "status": self.solver.StatusName(status)
        # and "runtime_seconds". It does NOT seem to return "success" key in metrics dict inside optimize().
        # However, app/main.py wraps it. Let's check app/main.py.
        # main.py: mlflow.log_metric("success", 1) but returns 'result' from opt.solve().
        # opt.solve() returns metrics dict.
        # Let's inspect what keys are in metrics.
        # keys: fairness_gap, shift_count, runtime_seconds, status.
        # So "success" key is NOT in data["metrics"].
        self.assertIn("status", data["metrics"])
        self.assertIn(data["metrics"]["status"], ["OPTIMAL", "FEASIBLE"])

    @patch("app.agent.genai.GenerativeModel")
    def test_agent_chat_endpoint(self, mock_genai_model):
        """Test /agent/chat with mocked LLM"""
        # Mock the LLM response
        mock_chat = MagicMock()
        mock_chat.send_message.return_value.text = """
        Analysis: User wants a shift.
        Action: UPDATE_SHIFT
        State: {"shifts": [{"name": "Morning", "start_time": 800, "duration_hours": 8, "staff_needed": 5}]}
        Reply: I have added the morning shift.
        """
        mock_genai_model.return_value.start_chat.return_value = mock_chat

        payload = {
            "message": "Add a morning shift for 5 people",
            "state": {"shifts": [], "month_year": "2023-10", "location": "Singapore"}
        }

        response = self.client.post("/agent/chat", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("reply", data)
        self.assertIn("updated_state", data)
        # Verify state update parsing logic worked (mocked response format dependent)
        # Note: The Agent logic parses the specific format returned by LLM.
        # If my mock text above matches the prompt structure expected by Agent, it should work.

        # Let's inspect the reply to ensuring it's not an error message
        self.assertNotIn("Error", data["reply"])

if __name__ == "__main__":
    unittest.main()
