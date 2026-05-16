"""LLM client for generating responses."""
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional, AsyncGenerator
from backend.config import Config


class LLMClient:
    """Client for interacting with OpenAI LLM."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.LLM_MODEL
    
    async def generate_response(
        self,
        user_question: str,
        context_docs: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Generate a response using RAG context and optional conversation history.

        Args:
            user_question: The user's question
            context_docs: List of relevant document chunks with metadata
            conversation_history: Optional list of {"role": "user"|"assistant", "content": "..."}
                for prior turns. Used to improve follow-up answers.

        Returns:
            Generated response string
        """
        # Build context from retrieved documents
        context = self._build_context(context_docs)

        # System prompt for Realtor Clause Assistant
        system_prompt = """You are a Realtor Clause Assistant. You help realtors choose and insert BCFSA clauses into contracts of purchase and sale.

Guidelines:
- Use only the information provided in the context to answer. The context contains clauses from the BCFSA knowledge base.
- When the realtor describes a scenario (e.g. subject to financing, tenant in the property, strata, deposit terms), recommend the right clause(s) and **include the full clause text** from the context so they can copy-paste it into the contract. Always mention the **Section** and **Clause** name.
- If the context does not contain a relevant clause, say so and suggest they check the BCFSA clauses page or speak to their managing broker.
- Be concise and practical. For follow-ups, use the prior messages and new context to give a coherent answer.

Disclaimer (include when recommending clauses): These clauses are for educational use only and do not constitute legal advice. Realtors should consult their managing broker and refer to the latest BCFSA clauses at bcfsa.ca when in doubt.

Formatting: Use Markdown—**bold** for section/clause names and key terms, bullet or numbered lists where helpful.
Put the exact clause wording inside ONE fenced code block using the language tag `text`, like ```text ... ``` so users can copy it.
Never emit an empty fenced block (do not open ``` and close ``` with no clause text between—every fence must contain the full wording from context).
If you cite multiple clauses, each clause gets its own non-empty fenced block."""

        # Current turn: context + question
        user_prompt = f"""Context from BCFSA clauses knowledge base:
{context}

Realtor's question: {user_question}

Answer using the context above. When recommending a clause, state the Section and Clause name, then provide the full clause text so the realtor can copy-paste it. Include the educational-use disclaimer if you are suggesting clause wording."""

        # Build messages: system, prior turns, current turn
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            for msg in conversation_history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )
        return response.choices[0].message.content

    async def generate_response_stream(
        self,
        user_question: str,
        context_docs: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream the response token-by-token. Same prompt as generate_response."""
        context = self._build_context(context_docs)
        system_prompt = """You are a Realtor Clause Assistant. You help realtors choose and insert BCFSA clauses into contracts of purchase and sale.

Guidelines:
- Use only the information provided in the context to answer. The context contains clauses from the BCFSA knowledge base.
- When the realtor describes a scenario (e.g. subject to financing, tenant in the property, strata, deposit terms), recommend the right clause(s) and **include the full clause text** from the context so they can copy-paste it into the contract. Always mention the **Section** and **Clause** name.
- If the context does not contain a relevant clause, say so and suggest they check the BCFSA clauses page or speak to their managing broker.
- Be concise and practical. For follow-ups, use the prior messages and new context to give a coherent answer.

Disclaimer (include when recommending clauses): These clauses are for educational use only and do not constitute legal advice. Realtors should consult their managing broker and refer to the latest BCFSA clauses at bcfsa.ca when in doubt.

Formatting: Use Markdown—**bold** for section/clause names and key terms, bullet or numbered lists where helpful.
Put the exact clause wording inside ONE fenced code block using the language tag `text`, like ```text ... ``` so users can copy it.
Never emit an empty fenced block (do not open ``` and close ``` with no clause text between—every fence must contain the full wording from context).
If you cite multiple clauses, each clause gets its own non-empty fenced block."""
        user_prompt = f"""Context from BCFSA clauses knowledge base:
{context}

Realtor's question: {user_question}

Answer using the context above. When recommending a clause, state the Section and Clause name, then provide the full clause text so the realtor can copy-paste it. Include the educational-use disclaimer if you are suggesting clause wording."""
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            for msg in conversation_history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_prompt})

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    def _build_context(self, context_docs: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved documents.
        
        Args:
            context_docs: List of document dictionaries
            
        Returns:
            Formatted context string
        """
        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            source = doc.get('metadata', {}).get('source', 'Unknown')
            text = doc.get('document', '')
            context_parts.append(f"[Source {i}: {source}]\n{text}\n")
        
        return "\n---\n".join(context_parts)
