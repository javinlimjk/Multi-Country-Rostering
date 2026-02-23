from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnablePassthrough

from app.rag.config import RAGConfig
from app.rag.retriever import get_retriever

# --- Pydantic Models for Structured Output ---

class Citation(BaseModel):
    law_name: str = Field(description="Name of the law or regulation (e.g. Employment Act 1955)")
    section: str = Field(description="Section number or clause (e.g. Section 60A(1))")
    excerpt: str = Field(description="Relevant text quoted from the law")
    url: Optional[str] = Field(description="Source URL or filename if available", default="")

class Violation(BaseModel):
    violation_type: str = Field(description="Type of violation (e.g. Max Hours, Rest Day, Overtime)")
    employee_id: str = Field(description="ID of the affected employee", default="N/A")
    description: str = Field(description="Detailed explanation of the violation in context of the roster")
    risk_level: str = Field(description="High, Medium, or Low")
    legal_basis: str = Field(description="Summary of the legal basis")
    citations: List[Citation] = Field(description="List of supporting legal citations")

class ComplianceReport(BaseModel):
    summary: str = Field(description="Executive summary of the audit findings")
    status: str = Field(description="PASS, FAIL, or WARNING")
    violations: List[Violation] = Field(description="List of detected violations")
    recommendations: List[str] = Field(description="Actionable recommendations to fix issues")
    confidence_score: float = Field(description="Confidence score (0.0 to 1.0) of the analysis")

# --- RAG Chain ---

def format_docs(docs):
    return "\n\n".join(f"--- SOURCE: {d.metadata.get('filename', 'Unknown')} ---\n{d.page_content}" for d in docs)

def get_compliance_chain():
    """
    Returns a Runnable chain that accepts {"query": str, "roster_data": str, "country": str}
    and returns a ComplianceReport object.
    """

    # 1. LLM
    if not RAGConfig.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set.")

    llm = ChatGoogleGenerativeAI(
        model=RAGConfig.LLM_MODEL,
        temperature=0,
        google_api_key=RAGConfig.GOOGLE_API_KEY
    )

    # 2. Retriever
    # Note: We need to bind the retriever dynamically or inside the chain?
    # For simplicity, we get a generic retriever here.
    # In a more advanced setup, we'd pass filters based on 'country' at runtime.
    # Here we will just retrieve broadly or let the LLM filter if we can't easily dynamic filter in LCEL.
    # Ideally, we use a RunnableLambda to build the retriever with filters.

    # Let's use a simpler approach: Retrieve based on the query text.
    retriever = get_retriever(k=5)

    # 3. Prompt
    template = """You are a Senior Labor Law Compliance Auditor.
Your task is to audit a workforce roster for compliance with labor laws.

### LEGAL CONTEXT (Retrieved Laws):
{context}

### ROSTER DATA (To Audit):
{roster_data}

### INSTRUCTIONS:
1. Analyze the roster data against the provided legal context.
2. Identify any violations of working hours, rest periods, overtime, or other regulations.
3. Be strict. If a rule says "max 44 hours", 45 is a violation.
4. Cite your sources specifically from the Legal Context. Do not hallucinate laws.
5. If the legal context is insufficient to judge, state that in the summary and lower confidence score.
6. Return the output in the specified JSON structure.

### QUESTION/FOCUS:
{query}

{format_instructions}
"""

    parser = PydanticOutputParser(pydantic_object=ComplianceReport)

    prompt = ChatPromptTemplate.from_template(
        template,
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    # 4. Chain
    # We define a chain that takes a dict: {query, roster_data, country}
    # We use RunnablePassthrough to pass inputs.
    # We assume 'retriever' is already set up.

    # Dynamic retrieval based on query + country is better.
    # But for now, we just use the text 'query' to retrieve.

    if retriever:
        chain = (
            {"context": (lambda x: x["query"] + " " + x.get("country", "")) | retriever | format_docs,
             "query": lambda x: x["query"],
             "roster_data": lambda x: x["roster_data"],
             "country": lambda x: x.get("country", "")}
            | prompt
            | llm
            | parser
        )
    else:
        # Fallback chain without context if retrieval fails
        print("⚠️ RAG Retriever not available. Running LLM without legal context.")
        chain = (
            {"context": lambda x: "LEGAL CONTEXT NOT AVAILABLE (RAG System Offline)",
             "query": lambda x: x["query"],
             "roster_data": lambda x: x["roster_data"],
             "country": lambda x: x.get("country", "")}
            | prompt
            | llm
            | parser
        )

    return chain

if __name__ == "__main__":
    # Test run
    try:
        chain = get_compliance_chain()
        res = chain.invoke({
            "query": "Check for maximum working hours violations.",
            "roster_data": "Staff A worked 50 hours.",
            "country": "SG"
        })
        print(res)
    except Exception as e:
        print(f"Chain setup failed: {e}")
