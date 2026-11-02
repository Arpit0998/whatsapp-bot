"""Glue between the pure engine and Django: load/save session, store messages and leads, alert staff."""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from django.db import transaction

from . import whatsapp
from .engine import Engine, format_lead_for_staff
from .models import ChatSession, Lead, Message

log = logging.getLogger(__name__)
engine = Engine()


@dataclass
class Result:
    replies: list
    lead: Optional[Lead]
    staff_message: Optional[str]


def already_processed(wa_message_id: str) -> bool:
    """Meta retries a webhook if we are slow; never answer the same message twice."""
    return bool(wa_message_id) and Message.objects.filter(wa_message_id=wa_message_id).exists()


def process_message(user_id: str, text: str, *, channel: str, phone: str = None, push_name: str = None,
                    wa_message_id: str = None) -> Result:
    """Run one customer message through the engine and persist everything in one transaction."""
    ctx = {"phone": phone, "push_name": push_name, "channel": channel}
    with transaction.atomic():
        Message.objects.create(user_id=user_id, channel=channel, direction=Message.Direction.IN, text=text,
                               wa_message_id=wa_message_id or None)
        session, _ = ChatSession.objects.select_for_update().get_or_create(user_id=user_id, defaults={"channel": channel})
        result = engine.handle(session.data or None, text, ctx)
        session.data = result["session"]
        session.channel = channel
        session.save()

        Message.objects.bulk_create(
            [Message(user_id=user_id, channel=channel, direction=Message.Direction.OUT, text=r["text"]) for r in result["replies"]]
        )

        lead = staff_message = None
        if result["lead"]:
            data = dict(result["lead"])
            if data.get("preferred_date"):  # engine keeps dates as "YYYY-MM-DD" strings
                data["preferred_date"] = date.fromisoformat(data["preferred_date"])
            lead = Lead.objects.create(**data)
            staff_message = format_lead_for_staff(result["lead"])
            log.info("New lead %s: %s - %s %s", lead.ref, lead.title, lead.name, lead.phone)

    return Result(result["replies"], lead, staff_message)


def alert_staff(staff_message: str) -> None:
    for number in whatsapp.staff_numbers():
        whatsapp.send_text(number, staff_message)


def reset_session(user_id: str) -> None:
    ChatSession.objects.filter(user_id=user_id).delete()
