"""Configuration settings for the backend."""
import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_env_file = _PROJECT_ROOT / ".env"
# Prefer values from project `.env` over pre-existing shell exports so local
# dev matches editing `.env` (stale OPENAI_API_KEY in ~/.zshrc won't win).
# Production usually has no `.env` on disk; the platform injects env vars instead.
load_dotenv(_env_file, override=True)

class Config:
    """Application configuration."""
    
    # OpenAI settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Vector database settings (separate from other Agent projects)
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./chroma_db_realtor_clauses")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "realtor_clauses")
    
    # API settings
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    
    # RAG settings
    TOP_K_RESULTS = 3  # Number of document chunks to retrieve
    CHUNK_SIZE = 1000  # Characters per chunk
    CHUNK_OVERLAP = 200  # Overlap between chunks

    # Input and timeouts
    MAX_QUESTION_LENGTH = int(os.getenv("MAX_QUESTION_LENGTH", "2000"))
    CHAT_TIMEOUT_SECONDS = float(os.getenv("CHAT_TIMEOUT_SECONDS", "90"))
    STREAM_CHUNK_TIMEOUT_SECONDS = float(os.getenv("STREAM_CHUNK_TIMEOUT_SECONDS", "60"))
    STREAM_TOTAL_TIMEOUT_SECONDS = float(os.getenv("STREAM_TOTAL_TIMEOUT_SECONDS", "120"))

    # Performance settings
    ENABLE_EMBEDDING_CACHE = True  # Cache embeddings for faster repeated queries

    # CORS — set FRONTEND_URL on Render to your Vercel URL to narrow origins in production
    FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip()

    # Slack — general feedback modal (text via incoming webhook; screenshots via bot API)
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "").strip()
    SLACK_FEEDBACK_CHANNEL_ID = os.getenv("SLACK_FEEDBACK_CHANNEL_ID", "").strip()
