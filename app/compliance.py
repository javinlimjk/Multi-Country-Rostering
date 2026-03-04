import os
import re
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

from app.rules import get_rules_for_country
from app.optimizer import validate_roster_logic
from app.rag.ingest import run_ingestion
from app.rag.retriever import get_retriever
from app.rag.chain import get_compliance_chain
import logging

logger = logging.getLogger(__name__)

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
        shift_map = {s['Name']: s for s in shift_definitions}

        staff_summaries = []

        # Group by staff
        # Check if 'staff_id' exists
        if 'staff_id' not in df.columns:
            return "Invalid assignment data: missing staff_id"

        for staff_id, group in df.groupby('staff_id'):
            group = group.sort_values('date')

            total_hours = 0
            consecutive_days = 0
            last_date = None
            shifts_details = []
            current_streak = 0

            for row in group.itertuples(index=False):
                shift_name = row.shift
                if shift_name in ['Off', 'Leave', 'MC'] or shift_name not in shift_map:
                    current_streak = 0
                    continue

                s_def = shift_map[shift_name]
                duration = s_def.get('Duration', 8)
                total_hours += duration

                if isinstance(row.date, str):
                    try:
                        date_obj = datetime.strptime(row.date, "%Y-%m-%d").date()
                    except:
                        continue # Skip invalid dates
                else:
                    date_obj = row.date

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

                shifts_details.append(f"{row.date}: {shift_name} ({duration}h)")

            summary = (
                f"Staff {staff_id}:\n"
                f"  - Total Hours: {total_hours}\n"
                f"  - Max Consecutive Days: {consecutive_days}\n"
                f"  - Shift Pattern: {', '.join(shifts_details[:5])}..."
            )
            staff_summaries.append(summary)

        return "\n".join(staff_summaries)

class ComplianceEngine:
    def __init__(self):
        """
        Initializes the Compliance Auditor Agent (RAG-enhanced).
        """
        logger.info("🧠 Loading Compliance Engine v2 (RAG)...")
        # RAG components are loaded on demand via app.rag modules

    def load_laws(self, directory_path: str):
        """
        Triggers the ingestion pipeline.
        """
        logger.info(f"📂 Scanning {directory_path} for legal documents...")
        try:
            run_ingestion(directory_path, force=True)
            logger.info("✅ Legal Knowledge Base Updated.")
        except Exception as e:
            logger.error(f"❌ Failed to load laws: {e}")

    def check_compliance(self, query: str, country_code: str = None, k: int = 3):
        """
        Standard RAG retrieval for search endpoint.
        """
        # We pass country_code to filter if supported, but currently filters
        # are only fully implemented for Pinecone in the retriever wrapper.
        filters = {"country": country_code} if country_code else None

        retriever = get_retriever(k=k, filters=filters)
        if not retriever:
            return ["RAG System not ready."]

        try:
            docs = retriever.invoke(query)
            # Filter results by country if simple retriever returned mixed results
            # (Simple client-side filtering)
            results = []
            for d in docs:
                content = d.page_content
                meta = d.metadata
                # If metadata has country and it doesn't match, skip?
                # But generic laws might have 'Global'.
                if country_code and meta.get('country') and meta.get('country') not in [country_code, 'Global']:
                    continue
                results.append(f"[Source: {meta.get('filename')}]\n{content}")
            return results
        except Exception as e:
            return [f"Retrieval error: {e}"]

    def audit_roster(self, assignments: List[Dict], shift_definitions: List[Dict], country_code: str) -> Dict:
        """
        Main Agent Function:
        1. Mask PII in assignments.
        2. Pre-process data.
        3. Deterministic Validation.
        4. RAG Chain Execution.
        """
        # Step 1: Mask PII explicitly
        masked_assignments = []
        id_map = {}
        next_id = 1

        for assignment in assignments:
            staff_id = assignment.get('staff_id')
            if staff_id not in id_map:
                id_map[staff_id] = f"Employee_{next_id}"
                next_id += 1

            masked_assignment = assignment.copy()
            masked_assignment['staff_id'] = id_map[staff_id]
            masked_assignments.append(masked_assignment)

        # Step 2: Pre-process
        masked_summary = AuditDataProcessor.process(masked_assignments, shift_definitions)

        # Step 3: Deterministic Validation
        # Use original assignments for deterministic validation so errors point to actual staff for the fallback
        rules = get_rules_for_country(country_code)
        deterministic_errors = validate_roster_logic(assignments, shift_definitions, rules)

        # Generate a masked version of deterministic errors so the LLM doesn't see real PII
        masked_deterministic_errors = validate_roster_logic(masked_assignments, shift_definitions, rules)

        det_error_str = "No algorithmic violations found."
        if masked_deterministic_errors:
            det_error_str = "CRITICAL ALGORITHMIC VIOLATIONS (Must be addressed):\n"
            for err in masked_deterministic_errors:
                det_error_str += f"- {err['type']}: {err['msg']}\n"

        # Step 4: RAG Chain
        chain = get_compliance_chain()
        
        # specific query focused on the roster context
        query = (
            f"Audit this roster for {country_code} labor law compliance. "
            f"Focus on working hours, rest days, and shift patterns. "
            f"Review the 'ALGORITHMIC VIOLATIONS' provided and confirm them with legal citations. "
            f"Algorithmic Findings: {det_error_str}"
        )

        try:
            logger.info("🤖 invoking RAG Chain...")
            result = chain.invoke({
                "query": query,
                "roster_data": masked_summary,
                "country": country_code
            })

            # Result is a ComplianceReport Pydantic object
            report = result.model_dump()

            # ADAPTER: Map to legacy frontend format to ensure UI compatibility
            legacy_report = {
                "verdict": report.get('status', 'UNKNOWN'),
                "summary": report.get('summary', ''),
                "violations": [],
                "recommendations": report.get('recommendations', [])
            }

            for v in report.get('violations', []):
                # Flatten citations for simple UI display
                citations_text = "; ".join([f"{c['law_name']} {c['section']}" for c in v.get('citations', [])])
                legacy_v = {
                    "type": v.get('violation_type', 'Unknown'),
                    "severity": v.get('risk_level', 'Medium'),
                    "description": v.get('description', ''),
                    "legal_citation": citations_text
                }
                legacy_report['violations'].append(legacy_v)

            return legacy_report

        except Exception as e:
            logger.error(f"❌ RAG Audit Failed: {e}")

            # Fallback to deterministic results if LLM fails
            logger.warning("⚠️ Falling back to deterministic logic only.")

            fallback_status = "FAIL" if deterministic_errors else "PASS"
            fallback_summary = "RAG Audit System unavailable. Report based on deterministic rules only."

            fallback_violations = []
            for err in deterministic_errors:
                fallback_violations.append({
                    "type": err['type'],
                    "severity": "High", # Deterministic errors are usually hard constraints
                    "description": err['msg'],
                    "legal_citation": "Algorithmic Check (Fallback)"
                })

            return {
                "verdict": fallback_status,
                "summary": fallback_summary,
                "violations": fallback_violations,
                "recommendations": ["Review technical violations manually."]
            }
