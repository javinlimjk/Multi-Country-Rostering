import pytest
from unittest.mock import MagicMock, patch
from app.compliance import ComplianceEngine

# Mock Data
MOCK_ASSIGNMENTS = [{"staff_id": "S1", "date": "2023-01-01", "shift": "Morning Ops"}]
MOCK_SHIFTS = [{"Name": "Morning Ops", "Duration": 8}]
MOCK_RULES = {}

@patch("app.compliance.get_compliance_chain")
@patch("app.compliance.validate_roster_logic")
@patch("app.compliance.get_rules_for_country")
def test_audit_roster_rag_failure_fallback(mock_get_rules, mock_validate, mock_get_chain):
    # Setup
    engine = ComplianceEngine()

    # Mock RAG failure
    mock_chain = MagicMock()
    mock_chain.invoke.side_effect = Exception("Rate Limit Exceeded")
    mock_get_chain.return_value = mock_chain

    # Mock Deterministic Errors (FAIL Case)
    mock_validate.return_value = [{"type": "Max Hours", "msg": "Worked too much"}]

    # Execute
    result = engine.audit_roster(MOCK_ASSIGNMENTS, MOCK_SHIFTS, "SG")

    # Assert
    assert result["verdict"] == "FAIL"
    assert "RAG Audit System unavailable" in result["summary"]
    assert len(result["violations"]) == 1
    assert result["violations"][0]["type"] == "Max Hours"
    assert result["violations"][0]["legal_citation"] == "Algorithmic Check (Fallback)"

@patch("app.compliance.get_compliance_chain")
@patch("app.compliance.validate_roster_logic")
@patch("app.compliance.get_rules_for_country")
def test_audit_roster_rag_failure_fallback_pass(mock_get_rules, mock_validate, mock_get_chain):
    # Setup
    engine = ComplianceEngine()

    # Mock RAG failure
    mock_chain = MagicMock()
    mock_chain.invoke.side_effect = Exception("API Error")
    mock_get_chain.return_value = mock_chain

    # Mock No Deterministic Errors (PASS Case)
    mock_validate.return_value = []

    # Execute
    result = engine.audit_roster(MOCK_ASSIGNMENTS, MOCK_SHIFTS, "SG")

    # Assert
    assert result["verdict"] == "PASS"
    assert "RAG Audit System unavailable" in result["summary"]
    assert len(result["violations"]) == 0
