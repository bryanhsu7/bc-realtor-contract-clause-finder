"""Rewrites follow-up questions into standalone queries for better retrieval."""
from openai import AsyncOpenAI
from typing import List, Dict
from backend.config import Config


class QueryRewriter:
    """Turns contextual follow-ups (e.g. 'What about the 5-year rule?') into standalone queries."""

    def __init__(self):
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.LLM_MODEL

    async def rewrite(
        self, question: str, conversation_history: List[Dict[str, str]]
    ) -> str:
        """Rewrite the question into a standalone form using prior messages.

        Args:
            question: The user's latest message (may be a follow-up).
            conversation_history: Prior user/assistant turns.

        Returns:
            A self-contained question suitable for embedding and retrieval.
        """
        history_str = "\n".join(
            f"{m['role']}: {m['content'][:500]}..."
            if len(m.get("content", "")) > 500
            else f"{m['role']}: {m['content']}"
            for m in conversation_history
        )
        prompt = f"""You are a search-query rewriter. Given a conversation and the user's latest message, output a single, self-contained question that could be used to search a knowledge base. The output must be one short sentence, with no preamble or explanation.

Conversation:
{history_str}

Latest user message: {question}

Standalone search query:"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150,
        )
        rewritten = (response.choices[0].message.content or question).strip()
        return rewritten if rewritten else question
