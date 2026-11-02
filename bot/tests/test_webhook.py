"""Webhook + web API tests. Outgoing WhatsApp calls are mocked, nothing leaves the machine."""

import hashlib
import hmac
import json
from unittest import mock

from django.test import TestCase, override_settings

from bot.models import ChatSession, Lead, Message

SECRET = "test-app-secret"


def wa_payload(text, msg_id="wamid.1", sender="919876543210", name="Rahul Sharma", kind="text"):
    msg = {"from": sender, "id": msg_id, "timestamp": "1762060000", "type": kind}
    if kind == "text":
        msg["text"] = {"body": text}
    elif kind == "image":
        msg["image"] = {"id": "img1", "mime_type": "image/jpeg"}
    elif kind == "reaction":
        msg["reaction"] = {"message_id": "wamid.0", "emoji": "👍"}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "15550000000", "phone_number_id": "123"},
            "contacts": [{"profile": {"name": name}, "wa_id": sender}],
            "messages": [msg],
        }}]}],
    }


@override_settings(WHATSAPP_TOKEN="t", WHATSAPP_PHONE_NUMBER_ID="123", WHATSAPP_VERIFY_TOKEN="verify-me",
                   WHATSAPP_APP_SECRET=SECRET, STAFF_NUMBERS=["9000000001"])
class WebhookTests(TestCase):
    def post(self, payload, secret=SECRET):
        body = json.dumps(payload).encode()
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post("/webhook/", data=body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=sig)

    def test_meta_verification_handshake(self):
        ok = self.client.get("/webhook/", {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
        self.assertEqual((ok.status_code, ok.content), (200, b"42"))
        bad = self.client.get("/webhook/", {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42"})
        self.assertEqual(bad.status_code, 403)

    @mock.patch("bot.whatsapp.mark_read")
    @mock.patch("bot.whatsapp.send_text", return_value=True)
    def test_rejects_bad_signature(self, send, _):
        r = self.post(wa_payload("hi"), secret="someone-else")
        self.assertEqual(r.status_code, 403)
        send.assert_not_called()

    @mock.patch("bot.whatsapp.mark_read")
    @mock.patch("bot.whatsapp.send_text", return_value=True)
    def test_hi_gets_greeting_and_menu(self, send, _):
        self.assertEqual(self.post(wa_payload("hi")).status_code, 200)
        self.assertEqual(send.call_count, 2)  # greeting + main menu
        to, text = send.call_args_list[0].args
        self.assertEqual(to, "919876543210")
        self.assertIn("Namaste Rahul", text)
        self.assertEqual(ChatSession.objects.get(user_id="919876543210").data["state"], "MAIN")

    @mock.patch("bot.whatsapp.mark_read")
    @mock.patch("bot.whatsapp.send_text", return_value=True)
    def test_duplicate_delivery_is_answered_once(self, send, _):
        self.post(wa_payload("hi", msg_id="wamid.same"))
        self.post(wa_payload("hi", msg_id="wamid.same"))
        self.assertEqual(send.call_count, 2)
        self.assertEqual(Message.objects.filter(wa_message_id="wamid.same").count(), 1)

    @mock.patch("bot.whatsapp.mark_read")
    @mock.patch("bot.whatsapp.send_text", return_value=True)
    def test_full_booking_creates_lead_and_alerts_staff(self, send, _):
        for i, text in enumerate(["hi", "1", "1", "1", "1", "1", "2", "1"]):
            self.post(wa_payload(text, msg_id=f"wamid.{i}"))
        lead = Lead.objects.get()
        self.assertEqual((lead.title, lead.model_name, lead.branch, lead.phone, lead.status),
                         ("Test Drive Booking", "Nissan Magnite", "Rohtak", "9876543210", "new"))
        staff_calls = [c for c in send.call_args_list if c.args[0] == "919000000001"]
        self.assertEqual(len(staff_calls), 1)
        self.assertIn(lead.ref, staff_calls[0].args[1])

    @mock.patch("bot.whatsapp.mark_read")
    @mock.patch("bot.whatsapp.send_text", return_value=True)
    def test_media_gets_text_only_hint_and_reactions_are_ignored(self, send, _):
        self.post(wa_payload("hi", msg_id="a"))
        send.reset_mock()
        self.post(wa_payload("", msg_id="b", kind="image"))
        self.assertIn("text messages only", send.call_args_list[0].args[1])
        send.reset_mock()
        self.post(wa_payload("", msg_id="c", kind="reaction"))
        send.assert_not_called()

    @mock.patch("bot.whatsapp.send_text", return_value=True)
    def test_status_updates_are_ignored(self, send):
        payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.1", "status": "read"}]}}]}]}
        self.assertEqual(self.post(payload).status_code, 200)
        send.assert_not_called()


class WebDemoApiTests(TestCase):
    def test_demo_page_renders(self):
        r = self.client.get("/")
        self.assertContains(r, "Autoveer WhatsApp Assistant")
        self.assertIn("csrftoken", r.cookies)

    def test_chat_api_runs_a_booking_and_saves_lead(self):
        self.client.get("/")
        for text in ["hi", "8", "Need fleet pricing for 5 Dost", "Amit Kumar", "9812000912"]:
            r = self.client.post("/api/chat/", data=json.dumps({"text": text}), content_type="application/json")
            self.assertEqual(r.status_code, 200)
        r = self.client.post("/api/chat/", data=json.dumps({"text": "1"}), content_type="application/json").json()
        self.assertEqual(r["lead"]["title"], "Callback Request")
        self.assertIn("New Callback Request", r["staff_message"])
        self.assertEqual(Lead.objects.get().channel, "web")

    def test_chat_api_booking_with_date(self):
        # regression: a lead with a preferred date used to crash the API response (HTTP 500)
        self.client.get("/")
        last = None
        for text in ["my tractor needs service", "hr12ab3456", "1", "2", "6", "Rahul Sharma", "9876543210", "1"]:
            last = self.client.post("/api/chat/", data=json.dumps({"text": text}), content_type="application/json")
            self.assertEqual(last.status_code, 200, text)
        lead = last.json()["lead"]
        self.assertEqual((lead["title"], lead["reg_no"], lead["branch"]), ("Service Booking", "HR12AB3456", "Bahadurgarh"))
        self.assertRegex(lead["preferred_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("Date:", last.json()["staff_message"])

    def test_reset_clears_session(self):
        self.client.post("/api/chat/", data=json.dumps({"text": "hi"}), content_type="application/json")
        self.assertEqual(ChatSession.objects.count(), 1)
        self.client.post("/api/chat/reset/")
        self.assertEqual(ChatSession.objects.count(), 0)
