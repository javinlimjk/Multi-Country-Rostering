import os
import pickle
from langchain.retrievers.ensemble import EnsembleRetriever
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
        # Load FAISS safely via native index and JSON metadata
        faiss_file = os.path.join(RAGConfig.FAISS_INDEX_PATH, "index.faiss")
        meta_file = os.path.join(RAGConfig.FAISS_INDEX_PATH, "index_meta.json")
        if os.path.exists(faiss_file) and os.path.exists(meta_file):
            try:
                import json
                import faiss
                from langchain_community.docstore.in_memory import InMemoryDocstore
                from langchain_core.documents import Document

                loaded_index = faiss.read_index(faiss_file)
                with open(meta_file, "r") as f:
                    data = json.load(f)

                loaded_docstore = InMemoryDocstore({k: Document(**v) for k, v in data["docstore"].items()})
                id_mapping = {k: v for k, v in data["id_mapping"].items()}
                if id_mapping:
                    id_mapping = {int(k): v for k, v in id_mapping.items()}

                vector_store = FAISS(
                    embedding_function=embeddings,
                    index=loaded_index,
                    docstore=loaded_docstore,
                    index_to_docstore_id=id_mapping
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
    bm25_path = os.path.join(RAGConfig.BASE_DIR, "bm25_docs.json")
    bm25_retriever = None

    if os.path.exists(bm25_path):
        try:
            import json
            from langchain_core.documents import Document
            with open(bm25_path, "r") as f:
                docs_dict = json.load(f)

            docs = [Document(**d) for d in docs_dict]
            if docs:
                bm25_retriever = BM25Retriever.from_documents(docs)
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
