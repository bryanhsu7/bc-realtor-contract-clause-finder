"""Vector database operations using Chroma."""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any
from backend.config import Config


class VectorStore:
    """Manages vector database operations."""
    
    def __init__(self):
        """Initialize Chroma client and collection."""
        self.client = chromadb.PersistentClient(
            path=Config.VECTOR_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    def clear_collection(self) -> None:
        """Delete and recreate the collection so it has no documents. Use before a fresh ingest."""
        self.client.delete_collection(name=Config.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_documents(
        self, 
        texts: List[str], 
        embeddings: List[List[float]], 
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ):
        """Add documents to the vector store.
        
        Args:
            texts: List of text chunks
            embeddings: List of embedding vectors
            metadatas: List of metadata dictionaries
            ids: List of unique IDs for each document
        """
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
    
    def search(
        self, 
        query_embedding: List[float], 
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents.
        
        Args:
            query_embedding: Embedding vector of the query
            top_k: Number of results to return
            
        Returns:
            List of dictionaries with 'document', 'metadata', and 'distance' keys
        """
        if top_k is None:
            top_k = Config.TOP_K_RESULTS
        
        # Optimize query - only fetch what we need
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Format results
        formatted_results = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else None
                })
        
        return formatted_results
    
    def get_collection_count(self) -> int:
        """Get the number of documents in the collection."""
        return self.collection.count()
