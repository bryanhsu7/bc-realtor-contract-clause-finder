"""In-memory store for thumbs-up/down feedback on assistant replies."""

from datetime import datetime
from typing import List, Optional


class FeedbackStore:
    """Stores per-turn feedback for analytics and tuning."""

    def __init__(self) -> None:
        self._entries: List[dict] = []

    def add(self, conversation_id: str, turn_index: int, helpful: bool) -> None:
        self._entries.append(
            {
                "conversation_id": conversation_id,
                "turn_index": turn_index,
                "helpful": helpful,
                "at": datetime.utcnow().isoformat() + "Z",
            }
        )

    def list_recent(self, limit: int = 100) -> List[dict]:
        return list(self._entries[-limit:])
