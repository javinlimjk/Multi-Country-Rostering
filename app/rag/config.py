import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class RAGConfig:
    # Embedding Model
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")

    # Vector Store
    VECTOR_STORE_TYPE = os.getenv("VECTOR_STORE_TYPE", "faiss") # 'faiss' or 'pinecone'
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_ENV = os.getenv("PINECONE_ENV")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "labor-laws")

    # LLM
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")

    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR = os.path.join(BASE_DIR, "data", "laws")
    FAISS_INDEX_PATH = os.path.join(BASE_DIR, "faiss_index")

    @classmethod
    def validate(cls):
        if cls.VECTOR_STORE_TYPE == "pinecone" and not cls.PINECONE_API_KEY:
            print("⚠️ Warning: PINECONE_API_KEY not set. Falling back to FAISS.")
            cls.VECTOR_STORE_TYPE = "faiss"

        if not cls.GOOGLE_API_KEY:
            print("⚠️ Warning: GOOGLE_API_KEY not set. LLM features will fail.")

RAGConfig.validate()
