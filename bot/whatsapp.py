"""WhatsApp Cloud API (Meta) client: webhook parsing, signature check and sending messages.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
"""

import hashlib
import hmac
import logging

import requests
from django.conf import settings

log = logging.getLogger(__name__)

MEDIA_TYPES = {"image", "video", "audio", "document", "sticker", "location", "contacts"}


def is_configured() -> bool:
    return bool(settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def verify_signature(raw_body: bytes, header: str) -> bool:
    """Meta signs every webhook with the app secret (X-Hub-Signature-256: sha256=<hex>)."""
    secret = settings.WHATSAPP_APP_SECRET
    if not secret:
        log.warning("WHATSAPP_APP_SECRET not set: skipping webhook signature check (OK for local testing only)")
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


def extract_messages(payload: dict):
    """Yield {id, from, name, text} for each customer message in a webhook payload.

    text is "" for media without a caption, so the bot can reply "text only".
    Status updates (sent/delivered/read), reactions and system messages are skipped.
    """
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                text = _message_text(msg)
                if text is None:
                    continue
                yield {"id": msg.get("id"), "from": msg.get("from"), "name": names.get(msg.get("from")), "text": text}


def _message_text(msg: dict):
    kind = msg.get("type")
    if kind == "text":
        return msg.get("text", {}).get("body", "")
    if kind == "interactive":
        inter = msg.get("interactive", {})
        return (inter.get("button_reply") or inter.get("list_reply") or {}).get("id", "")
    if kind == "button":  # quick-reply button on a template message
        return msg.get("button", {}).get("text", "")
    if kind in MEDIA_TYPES:
        return msg.get(kind, {}).get("caption", "") if isinstance(msg.get(kind), dict) else ""
    return None  # reaction, system, unsupported...


def send_text(to: str, body: str) -> bool:
    """Send a plain text message. Returns True on success; never raises."""
    if not is_configured():
        log.info("[WhatsApp not configured] would send to %s:\n%s", to, body)
        return False
    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body[:4096], "preview_url": False}},
            timeout=10,
        )
        if r.status_code >= 400:
            log.error("WhatsApp send to %s failed (%s): %s", to, r.status_code, r.text[:500])
            return False
        return True
    except requests.RequestException as e:
        log.error("WhatsApp send to %s failed: %s", to, e)
        return False


def mark_read(message_id: str) -> None:
    """Blue ticks for the customer (best effort)."""
    if not is_configured() or not message_id:
        return
    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    try:
        requests.post(url, headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
                      json={"messaging_product": "whatsapp", "status": "read", "message_id": message_id}, timeout=5)
    except requests.RequestException:
        pass


def staff_numbers() -> list:
    """STAFF_NUMBERS=9812000912,91XXXXXXXXXX -> ['919812000912', ...] (country code added for 10-digit numbers)."""
    out = []
    for n in settings.STAFF_NUMBERS:
        digits = "".join(ch for ch in n if ch.isdigit())
        if digits:
            out.append(f"91{digits}" if len(digits) == 10 else digits)
    return out
