import os
import sys
import unittest
import uuid
from unittest.mock import patch, MagicMock

# Mock out heavy dependencies
import sys

# Create a mock module structure for fastapi
mock_fastapi = MagicMock()
mock_fastapi.FastAPI = MagicMock
mock_fastapi.HTTPException = Exception  # Just use Exception for testing exception throws
mock_fastapi.Security = MagicMock()
mock_fastapi.status = MagicMock()
mock_fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR = 500
mock_fastapi.status.HTTP_403_FORBIDDEN = 403
mock_fastapi.Depends = MagicMock()

mock_security = MagicMock()
mock_security.APIKeyHeader = MagicMock

sys.modules['fastapi'] = mock_fastapi
sys.modules['fastapi.security'] = mock_security
sys.modules['pydantic'] = MagicMock()
sys.modules['mlflow'] = MagicMock()
sys.modules['app.models'] = MagicMock()
sys.modules['app.optimizer'] = MagicMock()
sys.modules['app.forecaster'] = MagicMock()
sys.modules['app.rules'] = MagicMock()
sys.modules['app.agent'] = MagicMock()
sys.modules['app.demand_planner'] = MagicMock()
sys.modules['app.rag.ingest'] = MagicMock()
sys.modules['app.rag.retriever'] = MagicMock()
sys.modules['app.rag.chain'] = MagicMock()
sys.modules['pandas'] = MagicMock()
sys.modules['celery'] = MagicMock()
sys.modules['celery.result'] = MagicMock()
sys.modules['app.tasks'] = MagicMock()

# Set up PYTHONPATH equivalent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import verify_api_key
from app.compliance import ComplianceEngine
import asyncio

class TestAPIKeyVerification(unittest.IsolatedAsyncioTestCase):
    async def test_verify_api_key_valid(self):
        result = await verify_api_key("secret123")
        self.assertTrue(result)

class TestUUIDMasking(unittest.TestCase):
    @patch('app.compliance.get_rules_for_country')
    @patch('app.compliance.validate_roster_logic')
    @patch('app.compliance.get_compliance_chain')
    @patch('app.compliance.AuditDataProcessor.process')
    def test_uuid_masking(self, mock_process, mock_get_chain, mock_validate, mock_rules):
        engine = ComplianceEngine()

        # Mock logic
        mock_rules.return_value = {}
        mock_validate.return_value = []

        mock_chain = MagicMock()
        mock_chain.invoke.return_value.model_dump.return_value = {
            'status': 'PASS',
            'summary': 'All good'
        }
        mock_get_chain.return_value = mock_chain

        assignments = [
            {'staff_id': 'Alice', 'date': '2023-01-01', 'shift': 'Morning'},
            {'staff_id': 'Alice', 'date': '2023-01-02', 'shift': 'Morning'},
            {'staff_id': 'Bob', 'date': '2023-01-01', 'shift': 'Afternoon'}
        ]

        shift_definitions = []

        # We need to capture the masked_assignments sent to mock_validate
        def validate_side_effect(assigns, defs, rules):
            # The second call to validate_roster_logic is with masked_assignments
            if len(assigns) > 0 and 'staff_id' in assigns[0] and '-' in assigns[0]['staff_id']:
                # Basic check for UUID format (contains hyphens)
                self.assertIn('-', assigns[0]['staff_id'])
                # Check mapping consistency
                self.assertEqual(assigns[0]['staff_id'], assigns[1]['staff_id']) # Alice
                self.assertNotEqual(assigns[0]['staff_id'], assigns[2]['staff_id']) # Bob
            return []

        mock_validate.side_effect = validate_side_effect

        engine.audit_roster(assignments, shift_definitions, "SG")

        self.assertEqual(mock_validate.call_count, 2)

if __name__ == '__main__':
    unittest.main()
