"""Feedback store — posts thumbs-up/down and general feedback to Slack."""

import json
import logging
import os
from datetime import datetime
from typing import List

import requests

from backend.config import Config

logger = logging.getLogger(__name__)


def _slack_webhook_url() -> str:
    return (os.environ.get("SLACK_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK") or "").strip()


def _webhook_response_ok(resp: requests.Response) -> bool:
    """Slack incoming webhooks usually return HTTP 200 and body ``ok``; some variants return JSON."""
    if resp.status_code != 200:
        return False
    t = (resp.text or "").strip()
    if not t or t == "ok":
        return True
    if t.startswith("{"):
        try:
            return bool(json.loads(t).get("ok"))
        except json.JSONDecodeError:
            return False
    return False


def _post_incoming_webhook(webhook_url: str, text: str) -> None:
    try:
        r = requests.post(
            webhook_url,
            json={"text": text},
            timeout=5,
        )
        if not _webhook_response_ok(r):
            logger.warning(
                "Slack webhook unexpected response: %s %s",
                r.status_code,
                (r.text or "")[:300],
            )
    except requests.RequestException as exc:
        logger.warning("Slack webhook request failed: %s", exc)


def _post_chat_message(token: str, channel: str, text: str) -> None:
    try:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"channel": channel, "text": text},
            timeout=10,
        )
        data = r.json() if r.text else {}
        if r.status_code != 200 or not data.get("ok"):
            logger.warning(
                "Slack chat.postMessage failed: %s %s",
                r.status_code,
                (data.get("error") or (r.text or ""))[:300],
            )
    except requests.RequestException as exc:
        logger.warning("Slack chat.postMessage request failed: %s", exc)


def _deliver_slack_text(text: str) -> None:
    """Post short text: prefer incoming webhook; else bot token + channel (needs chat:write)."""
    webhook_url = _slack_webhook_url()
    if webhook_url:
        _post_incoming_webhook(webhook_url, text)
        return
    token = (Config.SLACK_BOT_TOKEN or "").strip()
    channel = (Config.SLACK_FEEDBACK_CHANNEL_ID or "").strip()
    if token and channel:
        _post_chat_message(token, channel, text)
        return
    logger.warning(
        "Slack text notification skipped: set SLACK_WEBHOOK_URL (or SLACK_WEBHOOK) "
        "or both SLACK_BOT_TOKEN and SLACK_FEEDBACK_CHANNEL_ID"
    )


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
        _deliver_slack_text(
            f"{emoji} *{label}*  |  conv: `{conv_short}`"
            f"  |  turn: {turn_index}  |  {entry['at']}"
        )

    def send_general_feedback(self, message: str) -> None:
        _deliver_slack_text(f"💬 *User Feedback*\n{message}")

    def send_general_feedback_with_screenshot(
        self, message: str, image_bytes: bytes, filename: str
    ) -> None:
        token = (Config.SLACK_BOT_TOKEN or "").strip()
        channel = (Config.SLACK_FEEDBACK_CHANNEL_ID or "").strip()
        if not token or not channel:
            logger.warning(
                "Slack screenshot skipped: SLACK_BOT_TOKEN or SLACK_FEEDBACK_CHANNEL_ID missing"
            )
            return
        safe_name = os.path.basename(filename or "screenshot.png") or "screenshot.png"
        comment = (message or "").strip() or "(Screenshot only — no message)"
        initial_comment = f"💬 *User Feedback*\n{comment}"
        try:
            start = requests.post(
                "https://slack.com/api/files.getUploadURLExternal",
                headers={"Authorization": f"Bearer {token}"},
                data={
                    "filename": safe_name,
                    "length": str(len(image_bytes)),
                },
                timeout=30,
            )
            meta = start.json() if start.text else {}
            if start.status_code != 200 or not meta.get("ok"):
                logger.warning(
                    "Slack files.getUploadURLExternal failed: %s %s",
                    start.status_code,
                    (meta.get("error") or (start.text or ""))[:300],
                )
                return
            upload_url = meta.get("upload_url")
            file_id = meta.get("file_id")
            if not upload_url or not file_id:
                logger.warning("Slack upload URL response missing upload_url or file_id")
                return

            put = requests.post(
                upload_url,
                data=image_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=60,
            )
            if put.status_code != 200:
                put = requests.post(
                    upload_url,
                    files={"file": (safe_name, image_bytes, "image/png")},
                    timeout=60,
                )
            if put.status_code != 200:
                logger.warning(
                    "Slack file upload to upload_url failed: HTTP %s", put.status_code
                )
                return

            done = requests.post(
                "https://slack.com/api/files.completeUploadExternal",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={
                    "files": [{"id": file_id, "title": safe_name}],
                    "channel_id": channel,
                    "initial_comment": initial_comment,
                },
                timeout=60,
            )
            final = done.json() if done.text else {}
            if done.status_code != 200 or not final.get("ok"):
                logger.warning(
                    "Slack files.completeUploadExternal failed: %s %s",
                    done.status_code,
                    (final.get("error") or (done.text or ""))[:300],
                )
        except requests.RequestException as exc:
            logger.warning("Slack file upload request failed: %s", exc)

    def list_recent(self, limit: int = 100) -> List[dict]:
        return list(self._entries[-limit:])
