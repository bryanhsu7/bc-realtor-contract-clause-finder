"""Feedback store — posts thumbs-up/down events to Slack via Incoming Webhook."""

import json
import os
import urllib.request
from datetime import datetime
from typing import List


class FeedbackStore:
    """Stores per-turn feedback and forwards each event to a Slack channel."""

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
        self._notify_slack(entry)

    def list_recent(self, limit: int = 100) -> List[dict]:
        return list(self._entries[-limit:])

    def _notify_slack(self, entry: dict) -> None:
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return

        emoji = "👍" if entry["helpful"] else "👎"
        label = "Helpful" if entry["helpful"] else "Not helpful"
        conv_short = entry["conversation_id"][:8]
        text = (
            f"{emoji} *{label}*  |  conv: `{conv_short}`"
            f"  |  turn: {entry['turn_index']}  |  {entry['at']}"
        )

        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # Don't fail the feedback response if Slack is unreachable
