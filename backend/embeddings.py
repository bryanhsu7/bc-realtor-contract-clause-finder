"""Embedding generation using OpenAI."""
from openai import AsyncOpenAI
from typing import List, Dict
from backend.config import Config
import hashlib


class EmbeddingGenerator:
    """Generates embeddings for text using OpenAI."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.EMBEDDING_MODEL
        # Simple in-memory cache for embeddings
        self._cache: Dict[str, List[float]] = {}
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(f"{self.model}:{text}".encode(), usedforsecurity=False).hexdigest()
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text with caching.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        # Check cache first if enabled
        if Config.ENABLE_EMBEDDING_CACHE:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        # Generate embedding
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        embedding = response.data[0].embedding
        
        # Cache the result if enabled
        if Config.ENABLE_EMBEDDING_CACHE:
            self._cache[cache_key] = embedding
        
        return embedding
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()
    
    def get_cache_size(self) -> int:
        """Get the number of cached embeddings."""
        return len(self._cache)
