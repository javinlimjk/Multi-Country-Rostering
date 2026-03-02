import google.generativeai as genai
import os
import json
from typing import Optional, Dict, Any
from app.state import RosterState

class SchedulingAgent:
    """
    A conversational agent powered by Google Gemini to assist in roster configuration.
    Uses a stateful approach to incrementally gather shift details using Pydantic models.
    """

    def __init__(self):
        # Configure API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Warning: GOOGLE_API_KEY environment variable not found.")

        if api_key:
            genai.configure(api_key=api_key)

        # Using gemini-1.5-flash as the modern stable fallback.
        self.model_name = "gemini-2.5-flash-lite"
        self.model = genai.GenerativeModel(self.model_name)

    def process_message(self, user_text: str, current_state_dict: Dict[str, Any] = None) -> dict:
        """
        Process a natural language message from the user, updating the roster state.

        Args:
            user_text (str): The user's input message.
            current_state_dict (dict): The current state of the roster draft (dict representation of RosterState).

        Returns:
            dict: A dictionary containing:
                - 'reply': The agent's natural language response.
                - 'updated_state': The updated state dictionary.
                - 'is_complete': Boolean indicating if all fields are filled.
        """
        # Load state
        if current_state_dict:
            try:
                state = RosterState(**current_state_dict)
            except Exception:
                state = RosterState()
        else:
            state = RosterState()

        missing = state.missing_fields()
        is_complete_check = len(missing) == 0

        # System Instruction for the LLM
        system_prompt = f"""
        You are a Roster Configuration Assistant. Your goal is to help the user define a shift pattern AND trigger forecast or optimization actions.

        ### CURRENT STATE (JSON)
        {state.model_dump_json(indent=2)}

        ### MISSING INFORMATION
        {missing}

        ### INSTRUCTIONS
        1. **Extraction & State Management**:
           - Analyze the USER INPUT to extract NEW values.
           - MERGE new values with the `CURRENT STATE` provided above.
           - **CRITICAL**: You must return the FULL cumulative state. Do NOT drop existing shifts or data from `CURRENT STATE` unless the user explicitly asks to "delete" or "reset" them.
           - If the user provides shift details, append them to the 'shifts' list (or update if they are correcting a specific shift).
           - If the user provides a month/year, update 'month_year'.
           - 'start_time' must be int (e.g. 800). 'duration_hours' must be int. 'staff_needed' must be int.

        2. **Conversational Logic**:
           - DO NOT ask for fields that are already in `CURRENT STATE`.
           - ONLY ask for items listed in `MISSING INFORMATION` (if they are null in the state).
           - If `MISSING INFORMATION` is empty, summarize the extracted data.
           - **Action Detection**:
             - If the user asks to "forecast", "calculate requirements", "predict demand", or "how many staff do I need", set "action" to "FORECAST".
             - If the user asks to "generate roster", "optimize", "create schedule", "build roster", set "action" to "GENERATE".
             - Otherwise, "action" should be null.

        3. **Output Format**:
           Return a JSON object with:
           - "updated_state": The FULL updated state object (including OLD and NEW data) matching the RosterState structure.
           - "reply": Your natural language response to the user.
           - "is_complete": Boolean (true if no missing info, else false).
           - "action": String | null ("FORECAST" or "GENERATE").
        """

        try:
            full_prompt = f"{system_prompt}\n\nUSER INPUT: {user_text}"

            response = self.model.generate_content(
                full_prompt,
                generation_config={"response_mime_type": "application/json"}
            )

            text = response.text.strip()
            # Clean markdown codeblocks if they exist
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("\n", 1)[0]

            result = json.loads(text)

            # Validate return structure
            raw_updated_state = result.get("updated_state", state.model_dump())

            # Re-validate against Pydantic model to ensure type safety
            try:
                validated_state = RosterState(**raw_updated_state)
                updated_state_dict = validated_state.model_dump()
            except Exception as val_err:
                # Fallback to original state if LLM produced invalid schema, but keep the reply
                print(f"Agent state validation failed: {val_err}")
                updated_state_dict = state.model_dump()

            reply = result.get("reply", "I processed your request.")
            is_complete = result.get("is_complete", False)
            action = result.get("action", None)

            return {
                "reply": reply,
                "updated_state": updated_state_dict,
                "is_complete": is_complete,
                "action": action
            }

        except Exception as e:
            return {
                "reply": f"Sorry, I encountered an error processing your request: {str(e)}",
                "updated_state": state.model_dump(),
                "is_complete": False,
                "action": None
            }
