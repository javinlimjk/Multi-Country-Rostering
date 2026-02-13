
import unittest
import json
from unittest.mock import MagicMock, patch
# Set dummy API key to avoid warnings or skipped logic if any
import os
os.environ["GOOGLE_API_KEY"] = "dummy"

from app.agent import SchedulingAgent
from app.state import RosterState

class TestAgentValidation(unittest.TestCase):
    @patch("app.agent.genai.GenerativeModel")
    def test_invalid_state_handling(self, mock_genai_model):
        """Test that the agent handles invalid state from LLM gracefully"""
        # Mock the model instance
        mock_model_instance = MagicMock()
        mock_genai_model.return_value = mock_model_instance

        agent = SchedulingAgent()

        # Mock LLM returning valid JSON but invalid schema (missing 'staff_needed' in shift)
        response_payload = {
            "reply": "I added the shift.",
            "updated_state": {
                "shifts": [
                    {
                        "name": "Bad Shift",
                        "start_time": 800,
                        "duration_hours": 8
                        # 'staff_needed' is missing
                    }
                ],
                "location": "SG"
            },
            "is_complete": False,
            "action": None
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(response_payload)
        mock_model_instance.generate_content.return_value = mock_response

        # Initial empty state
        current_state = RosterState().model_dump()

        # Run process_message
        result = agent.process_message("Add bad shift", current_state)

        # Verify result
        # Since validation failed (Pydantic ValidationError), updated_state should match current_state (empty shifts)
        self.assertEqual(result['updated_state']['shifts'], [], "Should revert to original state on validation error")
        self.assertEqual(result['reply'], "I added the shift.", "Should still return the reply")

if __name__ == "__main__":
    unittest.main()
