# AI Implementation Report: Conversational Scheduling Agent

## 1. Executive Summary
This report documents the implementation of a Generative AI-powered conversational agent within the SATS Roster Optimization platform. The feature allows operational managers to configure complex shift patterns using natural language, bridging the gap between technical optimization algorithms and human-centric operations.

## 2. Technical Architecture & Integration
The solution demonstrates a "Hybrid AI" architecture, integrating deterministic operations research with probabilistic generative AI.

*   **Generative Layer (Knowledge Beyond Classroom):**
    *   **Model:** Google Gemini 1.5 Flash (`gemini-1.5-flash-001`).
    *   **Role:** Natural Language Understanding (NLU) and Entity Extraction. It converts unstructured text (e.g., "Add a morning shift for 5 people") into structured JSON data.
    *   **Implementation:** Leveraged `google-generativeai` SDK with "JSON Mode" to ensure deterministic output formats.

*   **Deterministic Layer (Classroom Knowledge):**
    *   **Core Engine:** Google OR-Tools (Constraint Programming).
    *   **Role:** Takes the structured inputs and mathematically solves the rostering problem to minimize cost and maximize fairness.
    *   **Integration:** The AI agent acts as a pre-processor for the optimization engine.

## 3. Analysis & Solution Formulation
A key technical challenge encountered was a "Dependency Hell" scenario involving Protocol Buffers (`protobuf`).

*   **The Problem:**
    *   The existing optimization engine (`ortools` v9.14+) required `protobuf >= 6.31.1`.
    *   The required Generative AI library (`google-generativeai`) depended on `google-ai-generativelanguage`, which strictly pinned `protobuf < 6.0.0`.
    *   This created a mutual exclusion preventing installation.

*   **The Formulation:**
    *   We analyzed the dependency trees of both critical components.
    *   We determined that `ortools` maintains Long-Term Support (LTS) compatibility for older `protobuf` versions in their v9.9 release stream.
    *   **Solution:** We strategically downgraded `ortools` to `9.9.3963` and pinned `protobuf` to `5.29.5`. This resolved the conflict without sacrificing core optimization capabilities, demonstrating pragmatic engineering over "always using the latest version."

## 4. Industry Relevance
This feature addresses a specific pain point in Applied AI: **Explainability and Accessibility.**
*   Optimization tools are often "Black Boxes" requiring complex configuration via CSVs or forms.
*   By adding a Chat Interface, we democratize access to high-end optimization, allowing non-technical shift managers to interact with the system intuitively. This is a current standard in modern Enterprise SaaS (e.g., Copilot integrations).

## 5. Implementation Details
*   **Backend:** FastAPI endpoint `/agent/chat` handling stateless interactions.
*   **Frontend:** Streamlit integration with session state management to provide a "live" chat experience.
*   **Robustness:**
    *   Specific model versioning (`-001` vs generic alias) to prevent 404 errors during model deprecation cycles.
    *   API Key validation and graceful error handling to prevent UI crashes.

## 6. Conclusion
The project successfully delivers a technically complex, industry-relevant feature. It integrates diverse AI domains (LLMs + OR) and demonstrates professional engineering practices through robust dependency management, testing, and modular design.
