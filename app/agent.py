import google.generativeai as genai
import os
import json
from typing import Optional, Dict, Any

class SchedulingAgent:
    """
    A conversational agent powered by Google Gemini to assist in roster configuration.
    Uses a stateful approach to incrementally gather shift details.
    """

    def __init__(self):
        # Configure API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Warning: GOOGLE_API_KEY environment variable not found.")

        if api_key:
            genai.configure(api_key=api_key)

        # Using gemini-1.5-flash-001 as it is a specific stable version.
        self.model_name = "gemini-1.5-flash-001"
        self.model = genai.GenerativeModel(self.model_name)

    def process_message(self, user_text: str, current_state: Dict[str, Any] = None) -> dict:
        """
        Process a natural language message from the user, updating the roster state.

        Args:
            user_text (str): The user's input message.
            current_state (dict): The current state of the roster draft.
                                  Structure: {'shift_name': ..., 'start_time': ..., 'duration': ..., 'staff_needed': ..., 'dates': ...}

        Returns:
            dict: A dictionary containing:
                - 'reply': The agent's natural language response.
                - 'updated_state': The updated state dictionary.
                - 'is_complete': Boolean indicating if all fields are filled.
        """
        if current_state is None:
            current_state = {
                "shift_name": None,
                "start_time": None,
                "duration": None,
                "staff_needed": None,
                "dates": None
            }

        # System Instruction for the LLM
        # We explicitly guide it to ONLY extract new info and merge with existing state
        system_prompt = f"""
        You are a Roster Configuration Assistant. Your goal is to help the user define a shift pattern.

        ### CURRENT STATE
        {json.dumps(current_state, indent=2)}

        ### INSTRUCTIONS
        1. Analyze the USER INPUT to extract NEW values for the missing fields.
        2. 'start_time' should be in 24-hour format (e.g., 800 for 08:00, 2300 for 23:00).
        3. 'duration' should be in hours.
        4. If the user provides a value that is already in CURRENT STATE, update it only if the user explicitly changes it.
        5. DO NOT ask for fields that are already filled (not null).
        6. If all fields are filled, set "is_complete" to true and ask for final confirmation to generate the roster.
        7. If fields are missing, ask specifically for them.

        ### OUTPUT FORMAT (JSON ONLY)
        {{
            "updated_state": {{
                "shift_name": "...",
                "start_time": 800,
                "duration": 8,
                "staff_needed": 5,
                "dates": "..."
            }},
            "reply": "Natural language response asking for missing fields or confirming readiness.",
            "is_complete": true/false
        }}
        """

        try:
            full_prompt = f"{system_prompt}\n\nUSER INPUT: {user_text}"

            response = self.model.generate_content(
                full_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            return {
                "reply": f"Sorry, I encountered an error processing your request: {str(e)}",
                "updated_state": current_state,
                "is_complete": False
            }
