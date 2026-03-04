import os
import shutil
from typing import List, Optional
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS, Pinecone
from langchain_core.documents import Document
from pinecone import Pinecone as PineconeClient, ServerlessSpec
from langchain_community.retrievers import BM25Retriever

from app.rag.config import RAGConfig

class IngestionPipeline:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name=RAGConfig.EMBEDDING_MODEL_NAME)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True
        )

    def load_documents(self, source_dir: str) -> List[Document]:
        """
        Loads documents from a directory. Supports .txt and .pdf.
        """
        if not os.path.exists(source_dir):
            print(f"⚠️ Source directory {source_dir} does not exist.")
            return []

        documents = []

        # Load .txt files
        txt_loader = DirectoryLoader(source_dir, glob="**/*.txt", loader_cls=TextLoader)
        try:
            txt_docs = txt_loader.load()
            print(f"📄 Loaded {len(txt_docs)} text documents.")
            documents.extend(txt_docs)
        except Exception as e:
            print(f"❌ Error loading .txt files: {e}")

        # Load .pdf files
        pdf_loader = DirectoryLoader(source_dir, glob="**/*.pdf", loader_cls=PyPDFLoader)
        try:
            pdf_docs = pdf_loader.load()
            print(f"📄 Loaded {len(pdf_docs)} PDF documents.")
            documents.extend(pdf_docs)
        except Exception as e:
            print(f"❌ Error loading .pdf files: {e}")

        return documents

    def process_documents(self, documents: List[Document]) -> List[Document]:
        """
        Chunks documents and enriches metadata.
        """
        if not documents:
            return []

        chunks = self.text_splitter.split_documents(documents)

        # Enrich metadata
        for chunk in chunks:
            source = chunk.metadata.get("source", "")
            filename = os.path.basename(source)
            chunk.metadata["filename"] = filename

            # Simple country extraction from filename (e.g., "sg_employment_act.txt")
            if "sg_" in filename.lower() or "singapore" in filename.lower():
                chunk.metadata["country"] = "SG"
            elif "my_" in filename.lower() or "malaysia" in filename.lower():
                chunk.metadata["country"] = "MY"
            elif "au_" in filename.lower() or "australia" in filename.lower():
                chunk.metadata["country"] = "AU"
            elif "uk_" in filename.lower() or "united_kingdom" in filename.lower():
                chunk.metadata["country"] = "UK"
            elif "us_" in filename.lower() or "united_states" in filename.lower():
                chunk.metadata["country"] = "US"
            else:
                chunk.metadata["country"] = "Global"

        print(f"✂️ Split into {len(chunks)} chunks.")
        return chunks

    def create_vector_store(self, chunks: List[Document], force_rebuild: bool = False):
        """
        Creates or updates the vector store and BM25 index.
        """
        if not chunks:
            print("⚠️ No chunks to index.")
            return None

        # Create/Update BM25 Retriever (Save it to JSON for hybrid search)
        try:
            import json
            print("Creating BM25 Retriever...")
            bm25_retriever = BM25Retriever.from_documents(chunks)
            bm25_path = os.path.join(RAGConfig.BASE_DIR, "bm25_docs.json")

            # Serialize documents to JSON instead of pickling the object
            docs_dict = [doc.dict() for doc in bm25_retriever.docs]
            with open(bm25_path, "w") as f:
                json.dump(docs_dict, f)
            print(f"✅ BM25 Documents saved to {bm25_path}")
        except Exception as e:
            print(f"❌ Failed to create BM25 Retriever: {e}")

        if RAGConfig.VECTOR_STORE_TYPE == "pinecone":
            return self._setup_pinecone(chunks)
        else:
            return self._setup_faiss(chunks, force_rebuild)

    def _setup_faiss(self, chunks: List[Document], force_rebuild: bool):
        index_path = RAGConfig.FAISS_INDEX_PATH

        faiss_file = os.path.join(index_path, "index.faiss")
        meta_file = os.path.join(index_path, "index_meta.json")

        if os.path.exists(faiss_file) and os.path.exists(meta_file) and not force_rebuild:
            print(f"Start loading existing FAISS index from {index_path}")
            try:
                import json
                import faiss
                from langchain_community.docstore.in_memory import InMemoryDocstore

                loaded_index = faiss.read_index(faiss_file)
                with open(meta_file, "r") as f:
                    data = json.load(f)

                loaded_docstore = InMemoryDocstore({k: Document(**v) for k, v in data["docstore"].items()})
                id_mapping = {k: v for k, v in data["id_mapping"].items()}
                if id_mapping:
                    id_mapping = {int(k): v for k, v in id_mapping.items()}

                vector_store = FAISS(
                    embedding_function=self.embeddings,
                    index=loaded_index,
                    docstore=loaded_docstore,
                    index_to_docstore_id=id_mapping
                )
                print("✅ FAISS index loaded successfully.")
                return vector_store
            except Exception as e:
                print(f"⚠️ Failed to load FAISS index: {e}. Rebuilding...")

        print("🏗️ Building new FAISS index...")
        import json
        import faiss

        vector_store = FAISS.from_documents(chunks, self.embeddings)

        # Save index natively
        os.makedirs(index_path, exist_ok=True)
        faiss.write_index(vector_store.index, os.path.join(index_path, "index.faiss"))

        # Extract docstore dict and id mapping safely
        docstore_dict = {k: v.dict() for k, v in vector_store.docstore._dict.items()}
        id_mapping = vector_store.index_to_docstore_id

        safe_path = os.path.join(index_path, "index_meta.json")
        with open(safe_path, "w") as f:
            json.dump({"docstore": docstore_dict, "id_mapping": id_mapping}, f)

        print(f"💾 FAISS index and metadata saved to {index_path}")
        return vector_store

    def _setup_pinecone(self, chunks: List[Document]):
        print("🌲 Setting up Pinecone...")
        if not RAGConfig.PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY is missing.")

        pc = PineconeClient(api_key=RAGConfig.PINECONE_API_KEY)
        index_name = RAGConfig.PINECONE_INDEX_NAME

        existing_indexes = [i.name for i in pc.list_indexes()]
        if index_name not in existing_indexes:
            print(f"Creating Pinecone index: {index_name}")
            pc.create_index(
                name=index_name,
                dimension=384, # Dimensions for all-MiniLM-L6-v2
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )

        # Use LangChain wrapper
        vector_store = Pinecone.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            index_name=index_name
        )
        print("✅ Pinecone index updated.")
        return vector_store

def run_ingestion(directory: str = RAGConfig.DATA_DIR, force: bool = True):
    pipeline = IngestionPipeline()
    docs = pipeline.load_documents(directory)
    chunks = pipeline.process_documents(docs)
    pipeline.create_vector_store(chunks, force_rebuild=force)

if __name__ == "__main__":
    run_ingestion()
