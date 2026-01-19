import google.generativeai as genai
import os
import json

class SchedulingAgent:
    """
    A conversational agent powered by Google Gemini to assist in roster configuration.

    This agent serves as a natural language interface for the rostering system.
    It takes unstructured user input (e.g., "I need a morning shift for 5 people")
    and extracts structured data (JSON) suitable for the optimization engine.
    """

    def __init__(self):
        """
        Initialize the SchedulingAgent.

        Configures the Google Generative AI client using the 'GOOGLE_API_KEY'
        environment variable and initializes the 'gemini-1.5-flash-001' model
        with specific system instructions for entity extraction.
        """
        # Configure API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            # For robustness in case env var is missing during dev/test.
            print("Warning: GOOGLE_API_KEY environment variable not found.")

        if api_key:
            genai.configure(api_key=api_key)

        # System Instruction for the LLM
        system_instruction = """You are a Roster Configuration Assistant. Your goal is to extract structured shift data from the user.
The user needs to define: Shift Name, Start Time (0-2359), Duration (hours), and Staff Count.

Output a JSON object with two keys:
1. 'reply': A natural language response to the user. If they missed the Date Range, ask for it. If they missed shift details (like start time), ask for them.
2. 'extracted_shifts': A list of objects [{'Name': str, 'Start Time': int, 'Duration': int, 'Staff Needed': int}] ONLY if the user provided enough info to define or update shifts. Otherwise null.

If the user provided shifts but NO dates, set 'reply' to: 'I have updated the shift patterns. What dates should I generate this for?'"""

        # Initialize the model
        # Using gemini-1.5-flash-001 as it is a specific stable version.
        self.model_name = "gemini-1.5-flash-001"
        self.model = genai.GenerativeModel(self.model_name, system_instruction=system_instruction)

    def process_message(self, user_text: str) -> dict:
        """
        Process a natural language message from the user.

        Args:
            user_text (str): The user's input message.

        Returns:
            dict: A dictionary containing:
                - 'reply': The agent's natural language response.
                - 'extracted_shifts': A list of extracted shift objects or None.
        """
        try:
            response = self.model.generate_content(
                user_text,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            # Fallback in case of API error or parsing error
            return {
                "reply": f"Sorry, I encountered an error processing your request with model {self.model_name}: {str(e)}",
                "extracted_shifts": None
            }
