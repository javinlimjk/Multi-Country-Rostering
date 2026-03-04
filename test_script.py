import sys
from unittest.mock import MagicMock

class MockBaseModel:
    def __init__(self, **kwargs):
        pass
    @classmethod
    def model_dump(cls): return {}

def MockField(*args, **kwargs):
    return None

mock_pydantic = MagicMock()
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = MockField
sys.modules['pydantic'] = mock_pydantic

sys.modules['fastapi'] = MagicMock()
mock_pandas = MagicMock()
sys.modules['pandas'] = mock_pandas
sys.modules['langchain'] = MagicMock()
sys.modules['langchain.retrievers'] = MagicMock()
sys.modules['langchain.retrievers.ensemble'] = MagicMock()
sys.modules['langchain_community'] = MagicMock()
sys.modules['langchain_community.document_loaders'] = MagicMock()
sys.modules['langchain_community.vectorstores'] = MagicMock()
sys.modules['langchain_community.retrievers'] = MagicMock()
sys.modules['langchain_text_splitters'] = MagicMock()
sys.modules['langchain_huggingface'] = MagicMock()
sys.modules['langchain_core'] = MagicMock()
sys.modules['langchain_core.documents'] = MagicMock()
sys.modules['langchain_core.prompts'] = MagicMock()
sys.modules['langchain_core.runnables'] = MagicMock()
sys.modules['langchain_core.output_parsers'] = MagicMock()
sys.modules['langchain_core.pydantic_v1'] = MagicMock()
sys.modules['langchain_google_genai'] = MagicMock()
sys.modules['pinecone'] = MagicMock()
sys.modules['mlflow'] = MagicMock()
sys.modules['streamlit'] = MagicMock()
sys.modules['ortools'] = MagicMock()
sys.modules['ortools.sat'] = MagicMock()
sys.modules['ortools.sat.python'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

from datetime import date
from enum import Enum
class Country(Enum):
    SG = "SG"

class MockShift:
    def __init__(self, id, date, start_time, duration_hours):
        self.id = id
        self.date = date
        self.start_time = start_time
        self.duration_hours = duration_hours

class MockStaff:
    def __init__(self, id):
        self.id = id

shifts = [
    MockShift("s1", date(2023, 10, 1), 800, 8),
    MockShift("s2", date(2023, 10, 1), 2000, 8)
]

staff = [MockStaff("staff1")]

from app.optimizer import RosterOptimizer

class DummyVar:
    def __add__(self, other):
        return self
    def __le__(self, other):
        return True

optimizer = RosterOptimizer.__new__(RosterOptimizer)
optimizer.shifts = shifts
optimizer.staff_list = staff
optimizer.rules = {'min_rest_hours': 10}
optimizer.assignments = {("staff1", "s1"): DummyVar(), ("staff1", "s2"): DummyVar()}
optimizer.model = MagicMock()

optimizer._apply_min_rest_period()
print("Min Rest Period ran! Constraint calls:", optimizer.model.Add.call_count)

from app.compliance import ComplianceEngine
import app.compliance
app.compliance.get_compliance_chain = MagicMock()
app.compliance.AuditDataProcessor.process = MagicMock(return_value="Masked summary")

mock_result = MagicMock()
mock_result.model_dump.return_value = {
    'status': 'PASS', 'summary': 'Tested properly', 'violations': [], 'recommendations': []
}
app.compliance.get_compliance_chain.return_value.invoke.return_value = mock_result

assignments = [
    {"staff_id": "real_123", "date": date(2023, 10, 1), "shift": "Morning"},
    {"staff_id": "real_123", "date": date(2023, 10, 2), "shift": "Morning"}
]
shift_definitions = [{"Name": "Morning", "Start Time": "0800", "Duration": "8.0", "Staff Needed": 1}]
engine = ComplianceEngine()
res = engine.audit_roster(assignments, shift_definitions, Country.SG.value)

print("Compliance ran! Masked results summary:", res['summary'])

# Verify that validate_roster_logic used Employee_1 for det_error_str
invoke_args = app.compliance.get_compliance_chain.return_value.invoke.call_args[0][0]

# Add a fake error by calling validate_roster_logic directly to see if PII was masked
# The actual logic in audit_roster runs validate_roster_logic. Let's create a violation.
assignments = [
    {"staff_id": "real_123", "date": date(2023, 10, 1), "shift": "Morning"},
    {"staff_id": "real_123", "date": date(2023, 10, 1), "shift": "Evening"} # Overlapping/No Rest
]
shift_definitions = [
    {"Name": "Morning", "Start Time": "0800", "Duration": "8.0", "Staff Needed": 1},
    {"Name": "Evening", "Start Time": "1600", "Duration": "8.0", "Staff Needed": 1}
]

res = engine.audit_roster(assignments, shift_definitions, Country.SG.value)
invoke_args = app.compliance.get_compliance_chain.return_value.invoke.call_args[0][0]
print("Query includes 'Employee_1':", "Employee_1" in invoke_args['query'])
print("Query includes 'real_123':", "real_123" in invoke_args['query'])
