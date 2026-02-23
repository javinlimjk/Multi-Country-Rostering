import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

# Ensure app is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.rag.ingest import IngestionPipeline
from app.rag.chain import get_compliance_chain, ComplianceReport
from app.rag.config import RAGConfig

# Mock Data
MOCK_DOC_TEXT = "Section 38: Employees shall not work more than 44 hours a week."

@pytest.fixture
def mock_laws_dir(tmp_path):
    # Create a dummy file
    laws_dir = tmp_path / "laws"
    laws_dir.mkdir()
    (laws_dir / "sg_employment_act.txt").write_text(MOCK_DOC_TEXT)
    return str(laws_dir)

def test_ingestion_pipeline_loading(mock_laws_dir):
    pipeline = IngestionPipeline()
    docs = pipeline.load_documents(mock_laws_dir)
    assert len(docs) == 1
    # Check simple text loading
    assert MOCK_DOC_TEXT in docs[0].page_content

def test_process_documents():
    pipeline = IngestionPipeline()
    doc = Document(page_content=MOCK_DOC_TEXT, metadata={"source": "data/laws/sg_employment_act.txt"})
    chunks = pipeline.process_documents([doc])
    assert len(chunks) > 0
    assert chunks[0].metadata["country"] == "SG"
    assert chunks[0].metadata["filename"] == "sg_employment_act.txt"

@patch("app.rag.chain.ChatGoogleGenerativeAI")
@patch("app.rag.chain.get_retriever")
def test_compliance_chain_construction(mock_get_retriever, mock_llm_cls):
    # Setup Mocks
    mock_retriever = MagicMock()
    mock_get_retriever.return_value = mock_retriever

    # Mock LLM
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm

    # Set API Key for config check
    with patch.object(RAGConfig, 'GOOGLE_API_KEY', 'dummy_key'):
        chain = get_compliance_chain()
        assert chain is not None

def test_compliance_report_schema():
    report = ComplianceReport(
        summary="Test Audit",
        status="PASS",
        violations=[],
        recommendations=["None"],
        confidence_score=0.95
    )
    assert report.status == "PASS"
    assert report.confidence_score == 0.95
