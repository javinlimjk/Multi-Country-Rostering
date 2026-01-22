# app/compliance.py
import os
import json
import pandas as pd
import numpy as np
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import faiss
from datetime import datetime, timedelta
from typing import List, Dict, Any

class AuditDataProcessor:
    """
    Helper class to pre-process roster data for the LLM.
    Calculates operational metrics like total hours, rest periods, etc.
    """
    @staticmethod
    def process(assignments: List[Dict[str, Any]], shift_definitions: List[Dict[str, Any]]) -> str:
        if not assignments:
            return "No assignments provided."

        # Convert to DataFrame
        df = pd.DataFrame(assignments)

        # Merge with shift definitions to get start/end times
        # assignments usually have 'shift' (name), 'date'.
        # shift_definitions have 'Name', 'Start Time', 'Duration'.

        # Create a lookup for shifts
        shift_map = {s['Name']: s for s in shift_definitions}

        staff_summaries = []

        # Group by staff
        for staff_id, group in df.groupby('staff_id'):
            group = group.sort_values('date')

            total_hours = 0
            consecutive_days = 0
            last_date = None
            shifts_details = []

            # Simple logic for consecutive days
            current_streak = 0

            # Iterate through assignments
            for _, row in group.iterrows():
                shift_name = row['shift']
                if shift_name in ['Off', 'Leave', 'MC'] or shift_name not in shift_map:
                    current_streak = 0
                    continue

                s_def = shift_map[shift_name]
                duration = s_def.get('Duration', 8)
                total_hours += duration

                date_obj = datetime.strptime(row['date'], "%Y-%m-%d").date()
                if last_date:
                    delta = (date_obj - last_date).days
                    if delta == 1:
                        current_streak += 1
                    else:
                        current_streak = 1
                else:
                    current_streak = 1

                consecutive_days = max(consecutive_days, current_streak)
                last_date = date_obj

                shifts_details.append(f"{row['date']}: {shift_name} ({duration}h)")

            summary = (
                f"Staff {staff_id}:\n"
                f"  - Total Hours: {total_hours}\n"
                f"  - Max Consecutive Days: {consecutive_days}\n"
                f"  - Shift Pattern: {', '.join(shifts_details[:5])}..."
            )
            staff_summaries.append(summary)

        return "\n".join(staff_summaries)

class ComplianceEngine:
    def __init__(self, embedding_model='all-MiniLM-L6-v2', llm_model='gemini-1.5-flash-001'):
        """
        Initializes the Compliance Auditor Agent.
        """
        print("🧠 Loading Compliance Engine...")

        # 1. Vector Store (Knowledge Base)
        self.embedder = SentenceTransformer(embedding_model)
        self.index = None
        self.documents = []
        self.doc_sources = []

        # 2. LLM (Auditor)
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.llm = genai.GenerativeModel(llm_model)
        else:
            print("⚠️ Warning: GOOGLE_API_KEY not found. Audit features disabled.")
            self.llm = None

    def load_laws(self, directory_path: str):
        if not os.path.exists(directory_path):
            print(f"⚠️ Warning: Directory {directory_path} not found.")
            return

        print(f"📂 Scanning {directory_path} for legal documents...")
        for filename in os.listdir(directory_path):
            if filename.endswith(".txt"):
                file_path = os.path.join(directory_path, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_chunks = f.read().split('\n\n')
                    for chunk in text_chunks:
                        if chunk.strip():
                            self.documents.append(chunk.strip())
                            self.doc_sources.append(filename)
        self._build_index()

    def _build_index(self):
        if not self.documents: return
        embeddings = self.embedder.encode(self.documents)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings))
        print("✅ Legal Knowledge Base Ready.")

    def check_compliance(self, query: str, country_code: str = None, k: int = 3):
        """
        Standard RAG retrieval.
        """
        if not self.index: return []
        query_vector = self.embedder.encode([query])
        distances, indices = self.index.search(query_vector, k=10) # Over-fetch for filtering
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.documents):
                doc_src = self.doc_sources[idx]
                # Filter by country code in filename (e.g. "sg_labor_law.txt")
                if country_code and country_code.lower() not in doc_src.lower():
                    continue
                
                results.append(self.documents[idx])
                if len(results) >= k: break
        return results

    def audit_roster(self, assignments: List[Dict], shift_definitions: List[Dict], country_code: str) -> Dict:
        """
        Main Agent Function:
        1. Pre-process data (AuditDataProcessor).
        2. Multi-Query Retrieval (Self-Querying).
        3. LLM Analysis with Rigid Template.
        """
        if not self.llm:
            return {"status": "Error", "message": "LLM not initialized."}

        # Step 1: Pre-process
        roster_summary = AuditDataProcessor.process(assignments, shift_definitions)

        # Step 2: Multi-Query Retrieval
        # We explicitly search for key compliance topics
        topics = ["Maximum working hours", "Rest periods between shifts", "Consecutive working days limit", "Overtime regulations"]
        legal_context_str = ""
        
        for topic in topics:
            laws = self.check_compliance(topic, country_code=country_code, k=2)
            if laws:
                legal_context_str += f"\n--- {topic} ---\n" + "\n".join(laws)

        if not legal_context_str:
            legal_context_str = "No specific legal documents found for this jurisdiction."

        # Step 3: Prompt Engineering (Auditor Template)
        prompt = f"""
        You are a Senior Compliance Auditor for Workforce Rosters. Your job is to strictly validate a proposed roster against provided legal regulations.

        ### LEGAL CONTEXT (Ground Truth)
        {legal_context_str}

        ### PROPOSED ROSTER SUMMARY (Data to Audit)
        {roster_summary}

        ### INSTRUCTIONS
        1. Analyze the Roster Summary against the Legal Context.
        2. Assign a Verdict: PASS, FAIL, or WARNING.
        3. You must cite specific sections from the Legal Context if you find a violation.
        4. If the Legal Context is missing specific numbers (e.g. "max hours"), acknowledge this limitation but flag high values as potential risks.

        ### OUTPUT FORMAT (JSON)
        {{
            "verdict": "PASS" | "FAIL" | "WARNING",
            "summary": "Brief executive summary of findings.",
            "violations": [
                {{
                    "type": "Max Hours" | "Rest Period" | "Consecutive Days" | "Other",
                    "description": "Explanation of the violation.",
                    "severity": "High" | "Medium" | "Low",
                    "legal_citation": "Quote from Legal Context or 'General Practice' if not found."
                }}
            ],
            "recommendations": ["Actionable advice 1", "Actionable advice 2"]
        }}

        Return ONLY valid JSON.
        """

        try:
            response = self.llm.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            return json.loads(response.text)
        except Exception as e:
            return {
                "verdict": "ERROR",
                "summary": f"Audit failed: {str(e)}",
                "violations": []
            }
