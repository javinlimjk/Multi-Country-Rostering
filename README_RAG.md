# RAG & Compliance Engine Architecture

## Overview
This module upgrades the compliance verification system from a simple keyword-based approach to a production-ready Retrieval Augmented Generation (RAG) system. It leverages Vector Search (Dense) and Keyword Search (Sparse/BM25) in a hybrid retrieval setup to ensure high recall and precision for labor law verification.

## Architecture

### 1. Ingestion Pipeline (`app/rag/ingest.py`)
- **Loaders**: Supports `.txt` and `.pdf` documents via LangChain loaders.
- **Splitting**: Uses `RecursiveCharacterTextSplitter` for semantic chunking (1000 chars, 200 overlap) to preserve context.
- **Metadata**: Automatically tags chunks with `country` (SG, MY, UK, etc.) and `source` filename.
- **Vector Store**:
  - **Local (Dev)**: FAISS (Facebook AI Similarity Search) for fast, local, CPU-based indexing.
  - **Production**: Pinecone (Serverless) for scalable, managed vector search. Configurable via `VECTOR_STORE_TYPE` env var.
- **Sparse Index**: Generates a BM25 index (pickled) during ingestion to support hybrid search.

### 2. Retrieval (`app/rag/retriever.py`)
- **Hybrid Search**: Implements `EnsembleRetriever` combining:
  - **Dense Retriever**: Semantic search using `sentence-transformers/all-MiniLM-L6-v2` embeddings.
  - **Sparse Retriever**: BM25 for precise keyword matching (e.g., specific section numbers).
- **Weights**: Configured to 60% Dense / 40% Sparse.

### 3. Reasoning Chain (`app/rag/chain.py`)
- **LLM**: Google Gemini 1.5 Flash (via `langchain-google-genai`) for cost-effective, high-context reasoning.
- **Structured Output**: Uses Pydantic models to enforce a strict JSON schema for the audit report, ensuring the UI can reliably parse violations and citations.
- **Prompt Engineering**: System prompt enforces the role of a "Strict Compliance Auditor" and requires evidence-based citations.

### 4. Security & Governance
- **PII Masking**: Names and IDs are masked (e.g., `Employee_ID_Masked`) before sending data to the LLM.
- **API Security**: `X-API-Key` header authentication required for compliance endpoints.
- **Fallback Strategy**: Robust error handling ensures that if the LLM/RAG system fails (e.g., rate limits, API errors), the system automatically falls back to deterministic logic, returning a report based solely on hard constraints (OR-Tools validation) marked as "Algorithmic Check (Fallback)".

## Usage

### Environment Variables
Create a `.env` file:
```bash
GOOGLE_API_KEY=your_gemini_key
PINECONE_API_KEY=your_pinecone_key (Optional)
VECTOR_STORE_TYPE=faiss (or pinecone)
COMPLIANCE_API_KEY=secret_key
```

### Ingestion
To rebuild the knowledge base:
```python
from app.rag.ingest import run_ingestion
run_ingestion("data/laws")
```
This runs automatically on server startup if the index is missing.

### API
- `POST /validate`: Triggers the audit.
- `GET /compliance/search`: Semantic search over laws.

## Trade-offs & Decisions
1.  **Hybrid Search**: Chosen because legal queries often involve specific terms ("Section 38") where dense embeddings might fail, but broad concepts ("overtime limits") where keyword search fails.
2.  **LangChain 0.2.x**: Pinned to stable 0.2.x release to resolve dependency conflicts between `langchain-google-genai` and `langchain-huggingface` in the current Python environment.
3.  **FAISS vs Pinecone**: FAISS allows zero-cost local development, while Pinecone provides the scale needed for enterprise deployment. The abstraction layer makes switching seamless.
