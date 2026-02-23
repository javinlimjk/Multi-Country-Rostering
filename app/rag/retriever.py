import os
import pickle
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS, Pinecone
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone import Pinecone as PineconeClient

from app.rag.config import RAGConfig

def get_retriever(k: int = 4, filters: dict = None):
    """
    Returns a Hybrid Retriever (Vector + BM25).
    """
    # 1. Vector Store Retriever
    embeddings = HuggingFaceEmbeddings(model_name=RAGConfig.EMBEDDING_MODEL_NAME)

    vector_store = None
    if RAGConfig.VECTOR_STORE_TYPE == "pinecone":
        if RAGConfig.PINECONE_API_KEY:
            # We don't initialize the full index object here to avoid overhead,
            # we let LangChain handle it or just use from_existing_index if possible
            # But langchain_community.vectorstores.Pinecone usually needs index_name
            vector_store = Pinecone.from_existing_index(
                index_name=RAGConfig.PINECONE_INDEX_NAME,
                embedding=embeddings
            )
    else:
        # Load FAISS
        if os.path.exists(RAGConfig.FAISS_INDEX_PATH):
            try:
                vector_store = FAISS.load_local(
                    RAGConfig.FAISS_INDEX_PATH,
                    embeddings,
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                print(f"⚠️ FAISS Load Error: {e}")

    if not vector_store:
        print("⚠️ No Vector Store found.")
        return None

    # Apply filters if supported (FAISS supports simple filters? Not easily in LC wrapper without generic helper)
    # Pinecone supports metadata filtering.
    search_kwargs = {"k": k}
    if filters and RAGConfig.VECTOR_STORE_TYPE == "pinecone":
        search_kwargs["filter"] = filters

    vs_retriever = vector_store.as_retriever(search_kwargs=search_kwargs)

    # 2. BM25 Retriever
    bm25_path = os.path.join(RAGConfig.BASE_DIR, "bm25_retriever.pkl")
    bm25_retriever = None

    if os.path.exists(bm25_path):
        try:
            with open(bm25_path, "rb") as f:
                bm25_retriever = pickle.load(f)
                bm25_retriever.k = k
        except Exception as e:
            print(f"⚠️ Failed to load BM25: {e}")

    if bm25_retriever:
        print("✅ Using Hybrid Search (Dense + Sparse).")
        return EnsembleRetriever(
            retrievers=[bm25_retriever, vs_retriever],
            weights=[0.4, 0.6] # Slightly favor dense
        )
    else:
        print("⚠️ BM25 missing. Using Dense Search only.")
        return vs_retriever
