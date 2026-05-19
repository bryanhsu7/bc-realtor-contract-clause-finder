"""In-memory conversation history store."""
import uuid
from collections import OrderedDict
from typing import Dict, List, Optional


class ConversationStore:
    """Stores recent messages per conversation for context in follow-up turns."""

    def __init__(self, max_turns: int = 10, max_conversations: int = 10000):
        """Initialize the store.

        Args:
            max_turns: Max user+assistant pairs to keep per conversation (default 10).
            max_conversations: Max distinct conversations before evicting the oldest (default 10000).
        """
        self._store: OrderedDict[str, List[Dict[str, str]]] = OrderedDict()
        self._max_turns = max_turns
        self._max_conversations = max_conversations

    def create_id(self) -> str:
        """Generate a new conversation id."""
        return str(uuid.uuid4())

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        """Append a message to a conversation. Trims to max_turns if needed."""
        if conversation_id not in self._store:
            if len(self._store) >= self._max_conversations:
                self._store.popitem(last=False)
            self._store[conversation_id] = []
        self._store.move_to_end(conversation_id)
        self._store[conversation_id].append({"role": role, "content": content})
        self._trim(conversation_id)

    def get_recent_messages(
        self, conversation_id: str, last_n_turns: int = 5
    ) -> List[Dict[str, str]]:
        """Return the last N user+assistant turns as a flat list of messages.

        Args:
            conversation_id: Conversation to load.
            last_n_turns: Number of user+assistant pairs (default 5).

        Returns:
            List of {"role": "user"|"assistant", "content": "..."}, oldest first.
        """
        if conversation_id not in self._store:
            return []
        messages = self._store[conversation_id]
        # Keep last (last_n_turns * 2) messages
        keep = last_n_turns * 2
        if len(messages) <= keep:
            return list(messages)
        return list(messages[-keep:])

    def _trim(self, conversation_id: str) -> None:
        """Keep only the last max_turns pairs per conversation."""
        if conversation_id not in self._store:
            return
        messages = self._store[conversation_id]
        max_messages = self._max_turns * 2
        if len(messages) > max_messages:
            self._store[conversation_id] = messages[-max_messages:]
