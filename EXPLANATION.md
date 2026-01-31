# Deep Dive: How Your CS Chatbot Works

This document explains the core concepts and implementation details of your chatbot.

## 🧠 Core Concept 1: RAG (Retrieval-Augmented Generation)

### The Problem RAG Solves

**Traditional LLM Limitation:**
- LLMs like GPT-4 are trained on data up to a certain date (knowledge cutoff)
- They don't know about YOUR company's specific documentation
- They can't access real-time information
- They might hallucinate (make up) answers

**RAG Solution:**
RAG combines two powerful techniques:
1. **Retrieval**: Find relevant information from YOUR knowledge base
2. **Augmentation**: Add that information to the LLM's context
3. **Generation**: LLM generates answer using BOTH its training AND your docs

### Visual Flow

```
User: "How do I reset my password?"
         ↓
[1] Convert question to embedding vector
         ↓
[2] Search vector database for similar document chunks
         ↓
[3] Retrieve top 3 most relevant chunks:
    - "To reset password, go to login page..."
    - "Password reset links expire after 24 hours..."
    - "Contact support if you don't receive email..."
         ↓
[4] Build prompt:
    System: "You are a helpful support agent..."
    Context: [Retrieved chunks above]
    User: "How do I reset my password?"
         ↓
[5] LLM generates answer using the context
         ↓
[6] Return: "To reset your password, go to the login page and click 
    'Forgot Password'. Enter your email and you'll receive a reset 
    link within 5 minutes..."
```

### Why This Works Better

- ✅ **Accurate**: Uses YOUR actual documentation
- ✅ **Up-to-date**: Add new docs anytime, no retraining needed
- ✅ **Transparent**: Shows which documents were used (sources)
- ✅ **Cost-effective**: Smaller, cheaper models work great with good context

---

## 🔢 Core Concept 2: Vector Embeddings

### What Are Embeddings?

**Simple Analogy:**
Think of embeddings like GPS coordinates for words/sentences:
- Words with similar meanings are "close together" in space
- "Dog" and "puppy" are nearby
- "Dog" and "airplane" are far apart

**Technical Definition:**
- Embeddings are arrays of numbers (vectors) that represent text
- Each number captures some aspect of meaning
- Similar texts → Similar vectors → Close in "vector space"

### Example

```
Question: "How do I reset my password?"
Embedding: [0.23, -0.45, 0.67, ..., 0.12]  (1536 numbers for OpenAI)

Document: "To reset your password, click Forgot Password..."
Embedding: [0.25, -0.43, 0.65, ..., 0.11]  (very similar!)

Distance: 0.05 (very close = very relevant)
```

### How We Use Embeddings

1. **During Ingestion** (one-time setup):
   - Take each document chunk
   - Convert to embedding vector
   - Store in vector database

2. **During Query** (every question):
   - Convert user question to embedding
   - Compare with all stored embeddings
   - Find closest matches (cosine similarity)

### Cosine Similarity Explained

**What it measures:**
- How similar two vectors are in direction
- Range: -1 (opposite) to 1 (identical)
- 0.9+ = very similar, 0.5 = somewhat similar, <0.3 = different

**Why it works:**
- Captures semantic meaning, not just keywords
- "Password reset" matches "forgot password" even though words differ

---

## 🗄️ Core Concept 3: Vector Database (Chroma)

### What is a Vector Database?

A specialized database optimized for:
- Storing vectors (embeddings)
- Fast similarity search
- Metadata filtering

### Why Not Regular Database?

**Regular SQL Database:**
```sql
SELECT * FROM docs WHERE text LIKE '%password%'
```
- Only finds exact keyword matches
- "reset password" won't match "forgot password"
- Slow for large text searches

**Vector Database:**
```python
vector_db.search(query_embedding, top_k=3)
```
- Finds semantic matches
- "reset password" matches "forgot password"
- Optimized for similarity search

### How Chroma Works

1. **Storage:**
   - Stores embeddings in optimized data structures (HNSW index)
   - Keeps metadata (source file, chunk index, etc.)
   - Persists to disk (local file)

2. **Search:**
   - Uses approximate nearest neighbor (ANN) algorithms
   - Returns top-k most similar vectors
   - Includes distance scores

3. **In Our Code:**
   ```python
   # Store
   vector_store.add_documents(
       texts=["chunk 1", "chunk 2"],
       embeddings=[[0.1, 0.2, ...], [0.3, 0.4, ...]],
       metadatas=[{"source": "faq.txt"}, {"source": "guide.md"}]
   )
   
   # Search
   results = vector_store.search(query_embedding, top_k=3)
   ```

---

## 🤖 Core Concept 4: LLM Prompt Engineering

### The Prompt Structure

Our LLM receives a carefully crafted prompt:

```
SYSTEM PROMPT:
"You are a helpful customer support agent for a company.
Your job is to answer customer questions accurately and helpfully 
using the provided context.

Guidelines:
- Use only the information provided in the context
- If context doesn't contain enough information, say 'I don't know'
- Be concise but thorough
- Be friendly and professional"

USER PROMPT:
"Context from knowledge base:
[Source 1: faq.txt]
To reset your password, go to the login page and click 
'Forgot Password'. Enter your email address...

[Source 2: guide.md]
Password reset links expire after 24 hours...

Customer Question: How do I reset my password?

Please provide a helpful answer based on the context above."
```

### Why This Structure?

1. **System Prompt**: Sets the AI's role and behavior
2. **Context**: Provides relevant information (from vector search)
3. **User Question**: The actual question to answer
4. **Instructions**: Tells AI how to use the context

### Key Prompt Engineering Principles

1. **Be Explicit**: Tell the AI exactly what to do
2. **Provide Examples**: Show desired format (if needed)
3. **Set Boundaries**: "Only use provided context"
4. **Handle Edge Cases**: "If you don't know, say so"

---

## 🔄 The Complete Flow (Step-by-Step)

### Phase 1: Setup (One-Time)

```
1. Add documents to knowledge_base/
   ├── faq.txt
   ├── product_guide.md
   └── policies.txt

2. Run ingestion script:
   python scripts/ingest_documents.py
   
3. For each document:
   a. Load text
   b. Split into chunks (1000 chars, 200 overlap)
   c. Generate embedding for each chunk
   d. Store in vector database with metadata
   
4. Result: Vector DB has 50 chunks ready to search
```

### Phase 2: User Query (Every Question)

```
1. User types a question (e.g. "What about the 5-year rule?" in a follow-up).
   
2. Frontend sends POST to /api/chat/stream (or /api/chat for non-streaming):
   { "question": "...", "conversation_id": "uuid" }   // omit conversation_id on first message

3. Backend (main.py):
   - Validates question (non-empty, length ≤ MAX_QUESTION_LENGTH)
   - Resolves conversation_id (create if missing), loads recent history from conversation_store
   - Calls rag_chain.query_stream(question, conversation_history) [or query() for JSON]

4. RAG Chain (rag_chain.py):
   a. If conversation_history exists: QueryRewriter turns the question into a standalone query
      (e.g. "What about the 5-year rule?" → "5-year rule for Roth IRA withdrawals")
   b. EmbeddingGenerator converts (rewritten or original) question to vector
   c. VectorStore returns top 3 chunks plus snippets
   d. LLMClient generates response (or stream), with context + conversation_history
   e. Returns/streams answer and sources (source, relevance_score, snippet)

5. Backend saves the turn to conversation_store; stream sends start → token… → done.

6. Frontend shows answer (plain while streaming, then Markdown), source list with "View snippet",
   and "Was this helpful?" 👍👎. Feedback is sent to POST /api/feedback and stored.
```

---

## 💬 Conversation Memory

**What it does:** Each thread has a `conversation_id`. The backend stores the last several user/assistant turns per conversation and sends them to the LLM with every new question so it can answer follow-ups ("What about the 5-year rule?", "Tell me more about that") in context.

**Flow:**
- First message: no `conversation_id` → backend creates one, returns it in the response. Frontend stores it and sends it on later messages.
- Later messages: frontend sends `conversation_id`; backend loads recent history from `conversation_store`, passes it into the RAG chain and LLM.
- **New conversation** in the UI clears `conversation_id` and message list so the next message starts a new thread.

**Where it lives:** `backend/conversation_store.py` (in-memory). History is trimmed to the last N turns (configurable) to keep prompts from growing without bound.

---

## 🔄 Query Rewriting (Follow-ups)

**What it does:** Short follow-ups like "What about the 5-year rule?" are ambiguous by themselves. Before we embed and search, we use the LLM to turn them into a **standalone** query (e.g. "5-year rule for Roth IRA withdrawals") using the last few turns of the conversation. We use that rewritten query for retrieval, and still send the **original** question to the LLM so the final answer matches what the user asked.

**Where it lives:** `backend/query_rewriter.py`. The RAG chain calls it only when `conversation_history` is present.

---

## 📡 Streaming

**What it does:** The default chat path uses **POST /api/chat/stream**. The backend runs RAG as usual, then streams the LLM reply token-by-token as Server-Sent Events (SSE). The frontend shows **plain text** while streaming to avoid re-rendering Markdown on every token; when the stream finishes it switches the same content to **Markdown** for formatting.

**Events:** `start` (sources + `conversation_id`), `token` (text deltas), `done`, and `error` (message). Conversation history is saved when `done` is sent.

**Non-streaming:** **POST /api/chat** still returns a single JSON object with `answer`, `sources`, `context_used`, `conversation_id` for clients that prefer it.

---

## ⏱️ Input Limits & Timeouts

- **Max question length:** `MAX_QUESTION_LENGTH` (default 2000). Longer questions get 400 with a clear message.
- **Non-streaming:** `CHAT_TIMEOUT_SECONDS` (default 90). If the full RAG+LLM run exceeds it, the API returns 504.
- **Streaming:** `STREAM_CHUNK_TIMEOUT_SECONDS` (default 60) is the max wait for the *next* event; `STREAM_TOTAL_TIMEOUT_SECONDS` (default 120) is the max duration of the whole stream. On timeout the stream sends an `error` event and stops.

All values are configurable via env (see `config.py`).

---

## 📎 Sources & “View Snippet”

Each source in the API includes a short **snippet** (e.g. first 300 characters of the chunk). The frontend lists sources and, when a snippet exists, offers **“View snippet”** to expand that text inline so users can see why a chunk was used. Snippets are returned in both the JSON chat response and the stream `start` event.

---

## 👍 Feedback (Was this helpful?)

Under each assistant answer (except the greeting), the UI shows **“Was this helpful?”** with 👍 and 👎. A click sends **POST /api/feedback** with `conversation_id`, `turn_index`, and `helpful: true/false`. The backend stores it in `feedback_store` (in-memory) for later use in tuning prompts or retrieval. The row then shows “Thanks for your feedback!” and hides the buttons.

---

## 📊 Code Walkthrough

### 1. RAG Chain (`backend/rag_chain.py`)

**Purpose**: Orchestrates the RAG pipeline, including optional query rewriting and streaming.

**Key methods:**
- **`query(question, conversation_history=None)`**  
  If there is history, the **query rewriter** turns the question into a standalone query for retrieval. We embed that (or the original question), search, then call the LLM with the **original** question and the retrieved chunks, plus `conversation_history` so the answer stays in context. Sources include a **snippet** (e.g. first 300 chars) for “View snippet” in the UI.

- **`query_stream(question, conversation_history=None)`**  
  Same retrieval and rewriting; then it yields `start` (sources + snippet), then token deltas from **`llm_client.generate_response_stream`**, then `done`. Used by **/api/chat/stream**.

### 2. Vector Store (`backend/vector_store.py`)

**Purpose**: Manages vector database operations

**Key Methods:**
- `add_documents()`: Store new documents
- `search()`: Find similar documents

**Chroma Setup:**
```python
self.client = chromadb.PersistentClient(path="./chroma_db")
self.collection = self.client.get_or_create_collection(
    name="cs_knowledge_base",
    metadata={"hnsw:space": "cosine"}  # Use cosine similarity
)
```

**Why Chroma:**
- Local (no cloud needed)
- Simple API
- Fast enough for MVP
- Can upgrade to Pinecone/Qdrant later

### 3. Embedding Generator (`backend/embeddings.py`)

**Purpose**: Converts text to embeddings

**OpenAI Embeddings:**
```python
response = self.client.embeddings.create(
    model="text-embedding-3-small",  # 1536 dimensions
    input=text
)
return response.data[0].embedding  # List of 1536 floats
```

**Why OpenAI:**
- High quality embeddings
- Consistent with their models
- Alternative: Use `sentence-transformers` (free, local)

### 4. LLM Client (`backend/llm_client.py`)

**Purpose**: Generates responses using context and optional conversation history.

**Methods:**
- **`generate_response(user_question, context_docs, conversation_history=None)`**  
  Builds the same system + user prompt. If `conversation_history` is provided, those messages are inserted after the system prompt and before the current “context + question” user message so follow-ups are coherent.

- **`generate_response_stream(...)`**  
  Same prompt construction, but calls the Chat API with `stream=True` and yields content deltas for SSE.

**Why this prompt structure:**
- Clear separation: System role vs. prior turns vs. context vs. question
- LLM knows to use context and history, not training data
- Easy to modify instructions

### 5. Document Ingestion (`scripts/ingest_documents.py`)

**Purpose**: Process documents and store in vector DB

**Chunking Strategy:**
```python
def chunk_text(text, chunk_size=1000, chunk_overlap=200):
    # Split into 1000-char chunks with 200-char overlap
    # Overlap ensures context isn't lost at boundaries
```

**Why chunking:**
- LLMs have token limits
- Smaller chunks = more precise retrieval
- Overlap = context preservation

**Metadata:**
```python
metadata = {
    'source': 'faq.txt',        # Which file
    'chunk_index': 2,            # Which chunk in file
    'total_chunks': 5            # Total chunks in file
}
```

**Why metadata:**
- Track where answers come from
- Show sources to users
- Debug retrieval issues

---

## 🎯 Key Design Decisions

### 1. Why Modular Architecture?

**Separate files for each component:**
- `embeddings.py` - Just embeddings
- `vector_store.py` - Just vector DB
- `llm_client.py` - Just LLM
- `rag_chain.py` - Orchestration

**Benefits:**
- Easy to test each component
- Easy to swap implementations (e.g., different vector DB)
- Clear separation of concerns
- Team members can work on different parts

### 2. Why Top-K = 3?

**Retrieving 3 chunks:**
- Balance between context and cost
- Too few (1-2): Might miss important info
- Too many (10+): Expensive, might include irrelevant info
- 3-5 is the sweet spot for most use cases

**You can adjust:**
```python
# In config.py
TOP_K_RESULTS = 5  # Try different values
```

### 3. Why Chunk Size = 1000?

**1000 characters per chunk:**
- Fits in LLM context window
- Large enough for complete thoughts
- Small enough for precise retrieval

**Overlap = 200:**
- Ensures sentences aren't split awkwardly
- Preserves context across chunk boundaries

### 4. Why GPT-4o-mini?

**Cost-effective model:**
- Much cheaper than GPT-4
- Still very capable with good context
- Fast response times
- Good for MVP

**You can upgrade:**
```python
# In config.py or .env
LLM_MODEL = "gpt-4"  # More capable, more expensive
```

---

## 🧪 Testing Your Understanding

### Question 1: What happens if you ask about something NOT in your knowledge base?

**Answer:**
1. Vector search returns chunks (might be irrelevant)
2. LLM sees context doesn't match question
3. LLM follows instructions: "If context doesn't contain enough info, say 'I don't know'"
4. Returns helpful fallback message

**Try it:** Ask "What's the weather today?" (not in your docs)

### Question 2: Why do we need embeddings? Can't we just search text directly?

**Answer:**
- Text search: "password reset" won't match "forgot password"
- Embedding search: Understands they mean the same thing
- Semantic understanding > keyword matching

### Question 3: What if a document is 10,000 characters?

**Answer:**
- Split into ~10 chunks (1000 chars each)
- Each chunk gets its own embedding
- Search might return multiple chunks from same document
- LLM combines them in context

---

## 🚀 Next Steps to Understand Deeper

1. **Conversation & streaming:** Use "New conversation" and multi-turn questions; watch plain text stream then switch to Markdown.

2. **Experiment with chunk sizes:** Try 500, 2000 characters in ingestion; see how it affects answer quality.

3. **Adjust TOP_K:** Try 1, 5, 10 results; compare answer quality.

4. **Modify prompts:** Change system prompt in `llm_client.py`; see how it affects responses.

5. **View snippet & feedback:** Click "View snippet" on sources; use thumbs up/down and inspect `feedback_store` or add persistence.

6. **Timeouts:** Set `CHAT_TIMEOUT_SECONDS` or `STREAM_CHUNK_TIMEOUT_SECONDS` in env to see 504 / stream error behavior.

7. **Monitor costs:** Check OpenAI usage dashboard; understand embedding vs. LLM costs.

---

## 📚 Further Reading

- **RAG Papers**: "Retrieval-Augmented Generation" by Facebook AI
- **Embeddings**: OpenAI Embeddings Guide
- **Vector DBs**: Chroma, Pinecone, Qdrant documentation
- **Prompt Engineering**: OpenAI Best Practices Guide

---

## 💡 Common Questions

**Q: Can I use a different LLM?**
A: Yes! Modify `llm_client.py` to use Anthropic Claude, local models, etc.

**Q: Can I use a different vector DB?**
A: Yes! Swap `vector_store.py` to use Pinecone, Qdrant, or Weaviate.

**Q: How do I add conversation memory?**
A: Already implemented. `conversation_store.py` keeps recent turns per `conversation_id`; the API loads them and passes `conversation_history` into the RAG chain and LLM. See “Conversation Memory” above.

**Q: How do I improve answer quality?**
A: Better documents, chunking, and prompts; query rewriting for follow-ups (already in place); optional reranking or multi-query retrieval.

**Q: Why plain text while streaming, then Markdown?**
A: Re-rendering Markdown on every token causes jank and layout jumps. Showing plain text until the stream is done, then switching to Markdown for the same content, keeps the UI smooth.

**Q: Where is feedback stored?**
A: In-memory in `feedback_store.py`. Persist by writing to a file or DB in the feedback endpoint, or forward to your analytics pipeline.

**Q: Is this production-ready?**
A: Good for an MVP: conversation memory, streaming, limits/timeouts, feedback, and source snippets are in place. For production, add: conversation (and optionally feedback) persistence, tighter CORS, rate limiting, and auth/monitoring as needed.
