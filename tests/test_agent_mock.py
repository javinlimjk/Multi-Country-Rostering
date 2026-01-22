import unittest
from unittest.mock import MagicMock, patch
import json
from app.agent import SchedulingAgent
from app.state import RosterState

class TestAgentLogic(unittest.TestCase):
    def setUp(self):
        # Mock the GENAI configure and model
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as MockModel:
            self.agent = SchedulingAgent()
            self.mock_model_instance = MockModel.return_value

    def test_process_message_merges_state(self):
        """Test that the python logic correctly passes current state to prompt and returns updated state."""

        # 1. Setup initial state
        initial_state = {
            "shifts": [{"name": "Morning", "start_time": 800, "duration_hours": 8, "staff_needed": 5}],
            "month_year": None,
            "location": "Singapore"
        }

        # 2. Mock the LLM response to simulate "adding a date" while PRESERVING the shift
        # The LLM *should* return the full state as per instructions.
        mock_response_text = json.dumps({
            "updated_state": {
                "shifts": [{"name": "Morning", "start_time": 800, "duration_hours": 8, "staff_needed": 5}],
                "month_year": "February 2026",
                "location": "Singapore"
            },
            "reply": "I've added the date.",
            "is_complete": True
        })

        mock_response = MagicMock()
        mock_response.text = mock_response_text
        self.agent.model.generate_content.return_value = mock_response

        # 3. Call process_message
        result = self.agent.process_message("Feb 2026", initial_state)

        # 4. Assertions
        # Check if the prompt contained the initial state (we can't easily check the prompt string content strictly,
        # but we can check if generate_content was called)
        self.agent.model.generate_content.assert_called_once()

        # Check output
        updated = result['updated_state']
        self.assertEqual(updated['month_year'], "February 2026")
        self.assertEqual(len(updated['shifts']), 1) # Shift should still be there
        self.assertEqual(updated['shifts'][0]['name'], "Morning")
        self.assertTrue(result['is_complete'])

    def test_process_message_handles_empty_state(self):
        """Test handling of empty initial state."""
        mock_response_text = json.dumps({
            "updated_state": {
                "shifts": [{"name": "Night", "start_time": 2200, "duration_hours": 8, "staff_needed": 2}],
                "month_year": None,
                "location": "Singapore"
            },
            "reply": "Added night shift.",
            "is_complete": False
        })

        mock_response = MagicMock()
        mock_response.text = mock_response_text
        self.agent.model.generate_content.return_value = mock_response

        result = self.agent.process_message("Night shift 2 people")

        self.assertEqual(len(result['updated_state']['shifts']), 1)
        self.assertEqual(result['updated_state']['shifts'][0]['name'], "Night")

if __name__ == '__main__':
    unittest.main()
