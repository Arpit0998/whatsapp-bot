"""Conversation tests: every flow of the bot, with a fixed clock (Mon 2 Nov 2026, 10:00 IST)."""

from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from bot.content import CONTENT
from bot.engine import Engine, clean_name, format_lead_for_staff, normalize_phone

NOW = datetime(2026, 11, 2, 4, 30, tzinfo=timezone.utc)
WA = {"phone": "919876543210", "push_name": "rahul sharma", "channel": "whatsapp"}


def chat(msgs, ctx=WA, now=NOW):
    engine = Engine(CONTENT, now=lambda: now, make_ref=lambda t: "AV-TEST")
    session, leads, last = None, [], None
    for m in msgs:
        last = engine.handle(session, m, ctx)
        session = last["session"]
        if last["lead"]:
            leads.append(last["lead"])
    text = "\n".join(r["text"] for r in last["replies"])
    return session, leads, text


class EngineFlowTests(SimpleTestCase):
    def test_greeting_uses_customer_name_and_shows_main_menu(self):
        session, _, text = chat(["hi"])
        self.assertIn("Namaste Rahul", text)
        self.assertIn("Nissan Cars", text)
        self.assertIn("Book a Service", text)
        self.assertEqual(session["state"], "MAIN")

    def test_magnite_test_drive_reuses_whatsapp_number(self):
        _, leads, text = chat(["hi", "1", "1", "1", "1", "1", "2", "1"])
        self.assertEqual(len(leads), 1)
        lead = leads[0]
        self.assertEqual(
            (lead["title"], lead["model_name"], lead["branch"], lead["preferred_date"], lead["name"], lead["phone"]),
            ("Test Drive Booking", "Nissan Magnite", "Rohtak", "2026-11-03", "Rahul Sharma", "9876543210"),
        )
        self.assertIn("Reference no: *AV-TEST*", text)

    def test_wording_depends_on_vehicle_kind(self):
        self.assertIn("Book a Demo", chat(["hi", "4", "1"])[2])
        self.assertIn("Book a Test Ride", chat(["hi", "2", "1"])[2])

    def test_price_quote_does_not_ask_for_date(self):
        _, leads, _ = chat(["hi", "2", "3", "2", "1", "4", "1"])
        self.assertEqual(leads[0]["title"], "On-road Price Quote")
        self.assertIsNone(leads[0]["preferred_date"])
        self.assertEqual(leads[0]["branch"], "Kurukshetra")

    def test_service_validates_reg_no_and_dates(self):
        self.assertIn("registration number looks incorrect", chat(["hi", "5", "2", "HR 1"])[2])
        self.assertIn("date does not exist", chat(["hi", "5", "2", "hr-12-ab-3456", "1", "31/02"])[2])
        self.assertIn("already passed", chat(["hi", "5", "2", "hr-12-ab-3456", "1", "01/10/2026"])[2])
        _, leads, _ = chat(["hi", "5", "2", "hr-12-ab-3456", "1", "15/11", "1", "1", "1"])
        self.assertEqual(leads[0]["reg_no"], "HR12AB3456")
        self.assertEqual(leads[0]["brand"], "Bajaj")
        self.assertEqual(leads[0]["preferred_date"], "2026-11-15")

    def test_free_text_tractor_service_prefills_brand(self):
        session, _, text = chat(["my tractor needs service"])
        self.assertEqual(session["flow"]["name"], "service")
        self.assertEqual(session["flow"]["data"]["brand_id"], "mf")
        self.assertIn("registration number", text)

    def test_keywords_jump_to_models_and_intents(self):
        self.assertIn("Ashok Leyland Bada Dost", chat(["hi", "bada dost price"])[2])
        self.assertIn("360° Around View", chat(["hi", "magnite"])[2])
        self.assertIn("insurance & finance", chat(["hi", "car insurance"])[2])
        self.assertIn("showrooms & service centres", chat(["hi", "showroom kahan hai"])[2])
        self.assertEqual(chat(["hi", "talk to executive"])[0]["flow"]["name"], "callback")

    def test_web_channel_asks_for_phone_and_validates_it(self):
        ctx = {"channel": "web"}
        self.assertIn("valid Indian mobile number", chat(["hi", "8", "Need fleet pricing for 5 Dost", "Amit Kumar", "12345"], ctx)[2])
        _, leads, _ = chat(["hi", "8", "Need fleet pricing for 5 Dost", "Amit Kumar", "+91 98120 00912", "yes"], ctx)
        self.assertEqual(leads[0]["phone"], "9812000912")
        self.assertEqual(leads[0]["title"], "Callback Request")

    def test_zero_goes_back_and_forgets_answer(self):
        session, _, text = chat(["hi", "1", "1", "1", "1", "3", "0"])
        self.assertNotIn("branch_id", session["flow"]["data"])
        self.assertIn("showroom / branch", text)
        self.assertEqual(chat(["hi", "1", "1", "0"])[0]["state"], "BRAND")

    def test_start_again_restarts_same_booking(self):
        session, _, text = chat(["hi", "1", "1", "1", "1", "1", "2", "2"])
        self.assertEqual(session["flow"]["name"], "sales")
        self.assertEqual(session["flow"]["data"]["model_id"], "magnite")
        self.assertIn("start again", text)

    def test_invalid_input_reshows_menu(self):
        session, _, text = chat(["hi", "42"])
        self.assertIn("didn't get that", text)
        self.assertEqual(session["state"], "MAIN")

    def test_cancel_inside_form(self):
        session, _, text = chat(["hi", "5", "cancel"])
        self.assertEqual(session["state"], "MAIN")
        self.assertIn("cancelled", text)

    def test_session_expires_after_30_minutes(self):
        engine = Engine(CONTENT, now=lambda: NOW)
        a = engine.handle(None, "hi", WA)
        b = engine.handle(a["session"], "1", WA)
        self.assertEqual(b["session"]["state"], "BRAND")
        later = Engine(CONTENT, now=lambda: NOW + timedelta(minutes=31))
        c = later.handle(b["session"], "1", WA)
        self.assertIn("Namaste", c["replies"][0]["text"])
        self.assertEqual(c["session"]["state"], "MAIN")

    def test_media_without_text_gets_hint(self):
        self.assertIn("text messages only", chat(["hi", ""])[2])

    def test_helpers(self):
        self.assertEqual(normalize_phone("+91 98120-00912"), "9812000912")
        self.assertEqual(normalize_phone("09812000912"), "9812000912")
        self.assertIsNone(normalize_phone("5812000912"))
        self.assertEqual(clean_name("  rahul   KUMAR 123 "), "Rahul KUMAR")
        self.assertIsNone(clean_name("a"))
        msg = format_lead_for_staff({"ref": "AV-1", "title": "Service Booking", "name": "X Y", "phone": "9812000912", "reg_no": ""})
        self.assertIn("New Service Booking", msg)
        self.assertNotIn("Reg no", msg)
