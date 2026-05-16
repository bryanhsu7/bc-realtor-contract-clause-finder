"""Feedback store — posts thumbs-up/down and general feedback to Slack."""

import json
import os
import urllib.request
from datetime import datetime
from typing import List


def _post_to_slack(text: str) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


class FeedbackStore:
    """Stores per-turn feedback and forwards events to Slack."""

    def __init__(self) -> None:
        self._entries: List[dict] = []

    def add(self, conversation_id: str, turn_index: int, helpful: bool) -> None:
        entry = {
            "conversation_id": conversation_id,
            "turn_index": turn_index,
            "helpful": helpful,
            "at": datetime.utcnow().isoformat() + "Z",
        }
        self._entries.append(entry)
        emoji = "👍" if helpful else "👎"
        label = "Helpful" if helpful else "Not helpful"
        conv_short = conversation_id[:8]
        _post_to_slack(
            f"{emoji} *{label}*  |  conv: `{conv_short}`"
            f"  |  turn: {turn_index}  |  {entry['at']}"
        )

    def send_general_feedback(self, message: str) -> None:
        _post_to_slack(f"💬 *User Feedback*\n{message}")

    def list_recent(self, limit: int = 100) -> List[dict]:
        return list(self._entries[-limit:])
