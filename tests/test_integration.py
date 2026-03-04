
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

    @patch("app.tasks.task_forecast.delay")
    def test_forecast_endpoint(self, mock_delay):
        """Test /forecast calculation"""
        mock_delay.return_value.id = "mock-task-id-1"
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
        self.assertIn("task_id", data)
        self.assertEqual(data["task_id"], "mock-task-id-1")

    @patch("app.tasks.task_optimize.delay")
    def test_optimize_endpoint_float_duration(self, mock_delay):
        """Test /optimize with float duration (Regression test for crash)"""
        mock_delay.return_value.id = "mock-task-id-2"
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
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["task_id"], "mock-task-id-2")

    @patch("app.tasks.task_agent_chat.delay")
    @patch("app.agent.genai.GenerativeModel")
    def test_agent_chat_endpoint(self, mock_genai_model, mock_delay):
        """Test /agent/chat with mocked LLM"""
        mock_delay.return_value.id = "mock-task-id-3"
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
        self.assertIn("task_id", data)
        self.assertEqual(data["task_id"], "mock-task-id-3")

if __name__ == "__main__":
    unittest.main()
