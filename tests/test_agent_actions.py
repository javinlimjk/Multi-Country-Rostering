import unittest
from unittest.mock import MagicMock, patch
import json
from app.agent import SchedulingAgent
from app.state import RosterState

class TestAgentActionLogic(unittest.TestCase):
    def setUp(self):
        # Mock the GENAI configure and model
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as MockModel:
            self.agent = SchedulingAgent()
            self.mock_model_instance = MockModel.return_value

    def test_process_message_detects_forecast_action(self):
        """Test that the agent detects FORECAST action."""

        initial_state = {
            "shifts": [{"name": "Morning", "start_time": 800, "duration_hours": 8, "staff_needed": 5}],
            "month_year": "Feb 2026",
            "location": "Singapore"
        }

        mock_response_text = json.dumps({
            "updated_state": initial_state,
            "reply": "Calculating requirements now.",
            "is_complete": True,
            "action": "FORECAST"
        })

        mock_response = MagicMock()
        mock_response.text = mock_response_text
        self.agent.model.generate_content.return_value = mock_response

        result = self.agent.process_message("How many staff do I need?", initial_state)

        self.assertEqual(result['action'], "FORECAST")

    def test_process_message_detects_generate_action(self):
        """Test that the agent detects GENERATE action."""

        initial_state = {
            "shifts": [{"name": "Morning", "start_time": 800, "duration_hours": 8, "staff_needed": 5}],
            "month_year": "Feb 2026",
            "location": "Singapore"
        }

        mock_response_text = json.dumps({
            "updated_state": initial_state,
            "reply": "Generating your roster.",
            "is_complete": True,
            "action": "GENERATE"
        })

        mock_response = MagicMock()
        mock_response.text = mock_response_text
        self.agent.model.generate_content.return_value = mock_response

        result = self.agent.process_message("Build the roster", initial_state)

        self.assertEqual(result['action'], "GENERATE")

if __name__ == '__main__':
    unittest.main()
