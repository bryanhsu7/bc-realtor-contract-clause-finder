"""RAG (Retrieval-Augmented Generation) chain implementation."""
from typing import Dict, Any, List, Optional, AsyncGenerator
from backend.embeddings import EmbeddingGenerator
from backend.vector_store import VectorStore
from backend.llm_client import LLMClient
from backend.query_rewriter import QueryRewriter


class RAGChain:
    """Orchestrates the RAG pipeline."""

    def __init__(self):
        """Initialize RAG components."""
        self.embedding_generator = EmbeddingGenerator()
        self.vector_store = VectorStore()
        self.llm_client = LLMClient()
        self.query_rewriter = QueryRewriter()

    async def query(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Process a user question through the RAG pipeline.

        Args:
            question: User's question
            conversation_history: Optional prior messages for this conversation

        Returns:
            Dictionary with 'answer', 'sources', and 'context_used' keys
        """
        # Step 0: For follow-ups, rewrite into a standalone query for retrieval
        query_for_retrieval = question
        if conversation_history:
            query_for_retrieval = await self.query_rewriter.rewrite(
                question, conversation_history
            )

        # Step 1: Generate embedding for the question (or rewritten query)
        question_embedding = await self.embedding_generator.generate_embedding(
            query_for_retrieval
        )

        # Step 2: Search vector database for similar documents
        search_results = self.vector_store.search(question_embedding)

        # Step 3: Check if we have relevant results
        if not search_results:
            return {
                "answer": "I don't have enough information in my knowledge base to answer that question. Please contact our support team for assistance.",
                "sources": [],
                "context_used": False,
            }

        # Step 4: Generate response using LLM with context and history
        answer = await self.llm_client.generate_response(
            question, search_results, conversation_history=conversation_history
        )
        
        # Step 5: Extract sources (with short snippet for "View source" UX)
        def _snippet(doc: dict, max_len: int = 300) -> str:
            text = (doc.get("document") or "").strip()
            return (text[:max_len] + "…") if len(text) > max_len else text

        sources = [
            {
                "source": doc.get("metadata", {}).get("source", "Unknown"),
                "relevance_score": 1 - doc.get("distance", 1.0),
                "snippet": _snippet(doc),
            }
            for doc in search_results
        ]
        
        return {
            "answer": answer,
            "sources": sources,
            "context_used": True,
        }

    async def query_stream(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream the RAG pipeline: start (with sources), token deltas, then done."""
        # Step 0: Rewrite follow-ups for retrieval
        query_for_retrieval = question
        if conversation_history:
            query_for_retrieval = await self.query_rewriter.rewrite(
                question, conversation_history
            )
        question_embedding = await self.embedding_generator.generate_embedding(
            query_for_retrieval
        )
        search_results = self.vector_store.search(question_embedding)

        if not search_results:
            yield {
                "type": "start",
                "sources": [],
                "context_used": False,
                "message": "I don't have enough information in my knowledge base to answer that question. Please contact our support team for assistance.",
            }
            yield {"type": "done"}
            return

        def _snippet(doc: dict, max_len: int = 300) -> str:
            text = (doc.get("document") or "").strip()
            return (text[:max_len] + "…") if len(text) > max_len else text

        sources = [
            {
                "source": doc.get("metadata", {}).get("source", "Unknown"),
                "relevance_score": 1 - doc.get("distance", 1.0),
                "snippet": _snippet(doc),
            }
            for doc in search_results
        ]
        yield {"type": "start", "sources": sources, "context_used": True}

        async for delta in self.llm_client.generate_response_stream(
            question, search_results, conversation_history=conversation_history
        ):
            yield {"type": "token", "delta": delta}
        yield {"type": "done"}
