# app/compliance.py
import os
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class ComplianceEngine:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        """
        Initializes the AI Model for text understanding.
        """
        print("🧠 Loading Language Model (This may take a moment)...")
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.documents = []
        self.doc_sources = []

    def load_laws(self, directory_path: str):
        """
        Reads all .txt files in the directory and indexes them.
        """
        if not os.path.exists(directory_path):
            print(f"⚠️ Warning: Directory {directory_path} not found.")
            return

        print(f"📂 Scanning {directory_path} for legal documents...")
        
        for filename in os.listdir(directory_path):
            if filename.endswith(".txt"):
                file_path = os.path.join(directory_path, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    # We split by double newlines to get "chunks" (paragraphs)
                    text_chunks = f.read().split('\n\n')
                    
                    for chunk in text_chunks:
                        if chunk.strip():
                            self.documents.append(chunk.strip())
                            self.doc_sources.append(filename)
                            
        self._build_index()

    def _build_index(self):
        """
        Converts text to vectors and stores them in FAISS.
        """
        if not self.documents:
            print("❌ No documents to index.")
            return

        print(f"🔢 Vectorizing {len(self.documents)} legal clauses...")
        embeddings = self.model.encode(self.documents)
        
        # Initialize FAISS Index (L2 Distance)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings))
        print("✅ Legal Knowledge Base Ready.")

    def check_compliance(self, query: str, country_code: str = None, k: int = 1):
        """
        Searches the database for laws relevant to the query.
        Supports filtering by country (e.g., 'SG', 'MY').
        """
        if not self.index:
            return [{"law_text": "System not initialized or no laws loaded.", "source": "System"}]

        # 1. Convert user query to vector
        query_vector = self.model.encode([query])
        
        # 2. Search FAISS index (Get top 10 to allow for filtering)
        distances, indices = self.index.search(query_vector, k=10)
        
        results = []
        # We assume batch size 1, so look at indices[0]
        for i, idx in enumerate(indices[0]):
            if idx < len(self.documents):
                doc_src = self.doc_sources[idx]
                doc_text = self.documents[idx]
                
                # --- FILTER LOGIC ---
                # Map "SG" -> "sg_labor_laws.txt", "MY" -> "my_labor_laws.txt"
                if country_code:
                    # e.g., if country_code is "MY", we check if "my" is in the filename "my_labor_laws.txt"
                    # Simple check: does the filename contain the country code (case-insensitive)?
                    required_tag = country_code.lower() 
                    if required_tag == "sg" and "sg_" not in doc_src.lower(): continue
                    if required_tag == "my" and "my_" not in doc_src.lower(): continue
                    if required_tag == "sa" and "sa_" not in doc_src.lower(): continue

                results.append({
                    "law_text": doc_text,
                    "source": doc_src,
                    "relevance_score": float(distances[0][i])
                })
                
                if len(results) >= k: break # Stop once we have enough filtered results
        
        return results if results else [{"law_text": "No specific regulation found for this jurisdiction.", "source": "System"}]