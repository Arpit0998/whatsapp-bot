import copy
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from urllib.parse import quote

from .content import CONTENT

IST = timezone(timedelta(hours=5, minutes=30))  

KEYCAPS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
RESET_WORDS = {"hi", "hii", "hiii", "hello", "helo", "hey", "menu", "main menu", "start", "restart", "namaste", "namaskar", "home", "#"}
CANCEL_WORDS = {"cancel", "stop", "exit", "quit"}
THANKS_WORDS = {"thanks", "thank you", "thankyou", "thx", "ok", "okay", "ok thanks", "dhanyawad", "shukriya", "great", "done"}
YES_WORDS = {"yes", "y", "haan", "ha", "han", "confirm", "ok", "okay"}
SKIP_WORDS = {"skip", "na", "n/a", "no", "none", "new", "nahi", "-"}
STOP_TOKENS = {"nissan", "bajaj", "ashok", "leyland", "massey", "ferguson", "other", "upcoming", "models", "range",
               "electric", "wheeler", "trucks", "buses", "implements", "ranges", "power"}
NAV = "_0 Back  •  MENU Main menu_"



def normalize_phone(value) -> Optional[str]:
    """'+91 98120-00912' / '09812000912' / '919812000912' -> '9812000912', else None."""
    if not value:
        return None
    d = re.sub(r"\D", "", str(value))
    if len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    return d if re.fullmatch(r"[6-9]\d{9}", d) else None


def clean_name(value) -> Optional[str]:
    if not value:
        return None
    s = "".join(c for c in str(value) if c.isalpha() or c in " .'")
    s = re.sub(r"\s+", " ", s).strip()
    if not 2 <= len(s) <= 40:
        return None
    # capitalise the first letter of each word, keep the rest as typed ("rahul KUMAR" -> "Rahul KUMAR")
    return " ".join(w[:1].upper() + w[1:] for w in s.split(" "))


def strip_emoji(s: str) -> str:
    # "So" covers almost every emoji; ℹ (U+2139) is classed as a letter, so drop it explicitly
    return "".join(c for c in str(s) if unicodedata.category(c) != "So" and c not in "️⃣ℹ").strip()


def fmt_date(ymd: str, with_year: bool = True) -> str:
    d = date.fromisoformat(ymd)
    out = f"{d:%a}, {d.day} {d:%b}"
    return f"{out} {d.year}" if with_year else out


def format_lead_for_staff(lead: dict) -> str:
    rows = [
        ("Ref", lead.get("ref")),
        ("Type", lead.get("title")),
        ("Brand", lead.get("brand")),
        ("Model", lead.get("model_name")),
        ("Vehicle", lead.get("vehicle_type")),
        ("Service", lead.get("service_type")),
        ("Reg no", lead.get("reg_no")),
        ("Message", lead.get("topic")),
        ("Date", fmt_date(lead["preferred_date"]) if lead.get("preferred_date") else None),
        ("Branch", lead.get("branch")),
        ("Name", lead.get("name")),
        ("Phone", lead.get("phone")),
        ("WhatsApp", lead.get("whatsapp") if lead.get("whatsapp") and lead.get("whatsapp") != lead.get("phone") else None),
    ]
    body = "\n".join(f"*{k}:* {v}" for k, v in rows if v)
    return f"🔔 *New {lead.get('title')}* (WhatsApp bot)\n\n{body}\n\n_Please call the customer back._"


def default_ref(t: datetime) -> str:
    return f"AV{t.astimezone(IST):%y%m%d}-{random.randint(1000, 9999)}"  # e.g. AV261102-4821


def reply(text: str, quick: Optional[list] = None) -> dict:
    return {"text": text, "quick": quick or []}


def num(n: int) -> str:
    return KEYCAPS[n] if n < len(KEYCAPS) else f"*{n}.*"


def numbered(items: list) -> str:
    return "\n".join(f"{num(i + 1)} {it['label']}" for i, it in enumerate(items))


def quick_from(items: list) -> list:
    return [{"reply": str(i + 1), "label": strip_emoji(it["label"])} for i, it in enumerate(items)]


def pick_number(low: str, maximum: int) -> int:
    """'3' -> 3 when 1..maximum, otherwise 0. '03' or '3a' are not numbers here."""
    if low.isdigit() and str(int(low)) == low and 1 <= int(low) <= maximum:
        return int(low)
    return 0


@dataclass
class Field:
    key: str
    ask: Callable  # (session, ctx) -> reply
    parse: Callable  # (raw, low, session, ctx) -> {"ok": value} | {"error": msg}
    skip: Callable = lambda data, ctx: False


# ---------------------------------------------------------------- engine

class Engine:
    FLOWS = {
        "sales": ["name", "phone", "branch", "date", "confirm"],
        "service": ["brand", "reg_no", "service_type", "date", "branch", "name", "phone", "confirm"],
        "insurance": ["ins_type", "vehicle_type", "reg_no", "name", "phone", "branch", "confirm"],
        "callback": ["topic", "name", "phone", "confirm"],
        "visit": ["date", "name", "phone", "confirm"],
    }

    def __init__(self, content: dict = CONTENT, now: Callable[[], datetime] = None, make_ref: Callable = None):
        self.c = content
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.make_ref = make_ref or default_ref
        self.timeout = timedelta(minutes=content.get("session_timeout_min", 30))
        self.brands = {b["id"]: b for b in content["brands"]}
        self.branches = {b["id"]: b for b in content["branches"]}

        co = content["company"]
        self.main_menu = [{"id": f"brand:{b['id']}", "label": f"{b['emoji']} {b['title']}"} for b in content["brands"]] + [
            {"id": "service", "label": "🔧 Book a Service"},
            {"id": "insurance", "label": "🛡️ Insurance & Finance"},
            {"id": "showroom", "label": "📍 Showrooms & Directions"},
            {"id": "executive", "label": "👤 Talk to an Executive"},
            {"id": "about", "label": f"ℹ️ About {co['short_name']}"},
        ]

        # model keywords for free text ("magnite price?", "pulsar", "241")
        self.model_index = []
        for b in content["brands"]:
            for m in b["models"]:
                for tok in re.split(r"[^a-z0-9]+", m["name"].lower()):
                    if tok and tok not in STOP_TOKENS and (len(tok) >= 4 or re.fullmatch(r"\d{3,}", tok)):
                        self.model_index.append((tok, b["id"], m["id"]))

        self.fields = self._build_fields()

    # ------------------------------------------------------------ small helpers
    def new_session(self, t: datetime = None) -> dict:
        return {"state": "MAIN", "sel": {}, "flow": None, "last_at": (t or self.now()).isoformat()}

    def _model(self, brand_id, model_id):
        b = self.brands.get(brand_id)
        return next((m for m in b["models"] if m["id"] == model_id), None) if b else None

    @staticmethod
    def _action_word(kind):
        return {"car": "Test Drive", "bike": "Test Ride"}.get(kind, "Demo")

    def _label(self, list_key, item_id):
        return next((x["label"] for x in self.c[list_key] if x["id"] == item_id), None)

    def _branch_items(self):
        return [{"id": b["id"], "label": b["city"] + (f" ({b['note']})" if b.get("note") else "")} for b in self.c["branches"]]

    # ------------------------------------------------------------ dates (IST, kept as YYYY-MM-DD strings)
    def _today(self) -> date:
        return self.now().astimezone(IST).date()

    def _date_options(self):
        t = self._today()
        d1, d2 = t + timedelta(days=1), t + timedelta(days=2)
        return [
            {"value": t.isoformat(), "label": f"Today ({fmt_date(t.isoformat(), False)})"},
            {"value": d1.isoformat(), "label": f"Tomorrow ({fmt_date(d1.isoformat(), False)})"},
            {"value": d2.isoformat(), "label": fmt_date(d2.isoformat(), False)},
        ]

    def _parse_date(self, low: str) -> dict:
        t = self._today()
        if low in ("today", "aaj"):
            return {"ok": t.isoformat()}
        if low in ("tomorrow", "kal", "tmrw"):
            return {"ok": (t + timedelta(days=1)).isoformat()}
        m = re.fullmatch(r"(\d{1,2})[/\-. ](\d{1,2})(?:[/\-. ](\d{2,4}))?", low)
        if not m:
            return {"error": "Please type the date like *15/11* or *15/11/2026*."}
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else t.year
        if y < 100:
            y += 2000
        try:
            picked = date(y, mo, d)
        except ValueError:
            return {"error": "That date does not exist. Please check and type again, e.g. *15/11*."}
        if not m.group(3) and picked < t:  # "05/01" typed in December means next January
            try:
                picked = picked.replace(year=y + 1)
            except ValueError:  # 29/02 with no leap year next year
                return {"error": "That date does not exist. Please check and type again, e.g. *15/11*."}
        diff = (picked - t).days
        if diff < 0:
            return {"error": "That date has already passed. Please choose today or a future date."}
        if diff > 90:
            return {"error": "We can book up to 90 days ahead. Please choose an earlier date."}
        return {"ok": picked.isoformat()}

    # ------------------------------------------------------------ form fields
    def _choice(self, key, prompt, items_fn, skip=None):
        def ask(s, ctx):
            items = items_fn()
            return reply(f"{prompt}\n\n{numbered(items)}\n\n{NAV}", quick_from(items))

        def parse(raw, low, s, ctx):
            items = items_fn()
            n = pick_number(low, len(items))
            if n:
                return {"ok": items[n - 1]["id"]}
            hit = next((it for it in items if strip_emoji(it["label"]).lower() == low or it["id"] == low), None)
            return {"ok": hit["id"]} if hit else {"error": f"Please reply with a number from 1 to {len(items)}."}

        return Field(key, ask, parse, skip or (lambda d, ctx: False))

    def _build_fields(self) -> dict:
        def ask_name(s, ctx):
            pn = clean_name(ctx.get("push_name"))
            if pn:
                return reply(f'May I know your *name*?\n\n{num(1)} Use "{pn}"\n_or type your name_', [{"reply": "1", "label": f'Use "{pn}"'}])
            return reply("May I know your *full name*?")

        def parse_name(raw, low, s, ctx):
            pn = clean_name(ctx.get("push_name"))
            if pn and low == "1":
                return {"ok": pn}
            v = clean_name(raw)
            return {"ok": v} if v else {"error": "Please type a valid name (letters only, 2-40 characters)."}

        def parse_phone(raw, low, s, ctx):
            p = normalize_phone(raw)
            return {"ok": p} if p else {"error": "That does not look like a valid Indian mobile number. Please type 10 digits, e.g. *98120 00912*."}

        def ask_date(s, ctx):
            opts = self._date_options()
            flow = s["flow"]
            if flow["name"] in ("service", "visit"):
                what = flow["name"]
            else:
                what = self._action_word(self.brands.get(flow["data"].get("brand_id"), {}).get("kind")).lower()
            return reply(f"📅 Which *date* suits you for the {what}?\n\n{numbered(opts)}\n\n_or type a date like 15/11_\n{NAV}", quick_from(opts))

        def parse_date(raw, low, s, ctx):
            opts = self._date_options()
            n = pick_number(low, len(opts))
            return {"ok": opts[n - 1]["value"]} if n else self._parse_date(low)

        def parse_reg(raw, low, s, ctx):
            if low in SKIP_WORDS:
                return {"ok": None}
            v = re.sub(r"[\s\-.]", "", raw.upper())
            if re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}", v) or re.fullmatch(r"\d{2}BH\d{4}[A-Z]{1,2}", v):
                return {"ok": v}
            return {"error": "That registration number looks incorrect. Please type it like *HR12AB3456*, or type *SKIP*."}

        def parse_topic(raw, low, s, ctx):
            v = re.sub(r"\s+", " ", raw.strip())
            return {"ok": v} if 2 <= len(v) <= 300 else {"error": "Please type a short message (up to 300 characters)."}

        def ask_confirm(s, ctx):
            lines = "\n".join(self._summary_lines(s["flow"]))
            return reply(
                f"Please *confirm* your details:\n\n{lines}\n\n{num(1)} ✅ Confirm\n{num(2)} ✏️ Start again\n{NAV}",
                [{"reply": "1", "label": "Confirm"}, {"reply": "2", "label": "Start again"}],
            )

        def parse_confirm(raw, low, s, ctx):
            if low == "1" or low in YES_WORDS:
                return {"ok": True}
            if low in ("2", "edit"):
                return {"ok": False}
            return {"error": "Reply *1* to confirm or *2* to start again."}

        c = self.c
        return {
            "name": Field("name", ask_name, parse_name),
            "phone": Field("phone", lambda s, ctx: reply("Please share your *10-digit mobile number* so our team can call you."),
                           parse_phone, skip=lambda d, ctx: bool(normalize_phone(ctx.get("phone")))),
            "branch": self._choice("branch_id", "📍 Which *showroom / branch* is convenient for you?", self._branch_items),
            "date": Field("date", ask_date, parse_date, skip=lambda d, ctx: bool(d.get("interest")) and d.get("interest") != "test_drive"),
            "brand": self._choice("brand_id", "Which *brand* is your vehicle?",
                                  lambda: [{"id": b["id"], "label": f"{b['emoji']} {b['name']}"} for b in c["brands"]],
                                  skip=lambda d, ctx: bool(d.get("brand_id"))),
            "reg_no": Field("reg_no",
                            lambda s, ctx: reply("Please type your *vehicle registration number* (e.g. HR12AB3456).\n\n_Type SKIP if you do not have it handy._",
                                                 [{"reply": "skip", "label": "Skip"}]),
                            parse_reg, skip=lambda d, ctx: d.get("ins_type") in ("new", "loan")),
            "service_type": self._choice("service_type", "🔧 What do you need?", lambda: c["service_types"]),
            "ins_type": self._choice("ins_type", "🛡️ How can we help with *insurance & finance*?", lambda: c["insurance_types"]),
            "vehicle_type": self._choice("vehicle_type", "Which *type of vehicle* is it for?", lambda: c["vehicle_types"]),
            "topic": Field("topic", lambda s, ctx: reply("👤 Sure! Briefly tell us *what you would like to discuss* and an executive will call you back."), parse_topic),
            "confirm": Field("confirmed", ask_confirm, parse_confirm),
        }

    # ------------------------------------------------------------ lead text
    def _lead_title(self, flow) -> str:
        d = flow["data"]
        if flow["name"] == "sales":
            if d.get("interest") == "test_drive":
                return f"{self._action_word(self.brands.get(d.get('brand_id'), {}).get('kind'))} Booking"
            return "On-road Price Quote" if d.get("interest") == "price_quote" else "Finance / EMI Enquiry"
        return {
            "service": "Service Booking",
            "insurance": self._label("insurance_types", d.get("ins_type")) or "Insurance",
            "callback": "Callback Request",
        }.get(flow["name"], "Showroom Visit")

    def _summary_lines(self, flow) -> list:
        d = flow["data"]
        lines = [f"📝 *{self._lead_title(flow)}*"]
        model = self._model(d.get("brand_id"), d.get("model_id")) if d.get("model_id") else None
        if model:
            lines.append(f"🚘 {model['name']}")
        elif d.get("brand_id"):
            lines.append(f"🏷️ {self.brands[d['brand_id']]['name']}")
        if d.get("vehicle_type"):
            lines.append(f"🚘 {self._label('vehicle_types', d['vehicle_type'])}")
        if d.get("service_type"):
            lines.append(f"🔧 {self._label('service_types', d['service_type'])}")
        if "reg_no" in d:
            lines.append(f"🔢 {d['reg_no'] or 'Reg. no. not provided'}")
        if d.get("topic"):
            lines.append(f"💬 {d['topic']}")
        if d.get("date"):
            lines.append(f"📅 {fmt_date(d['date'])}")
        if d.get("branch_id"):
            lines.append(f"📍 {self.branches[d['branch_id']]['city']}")
        if d.get("name"):
            lines.append(f"👤 {d['name']}")
        if d.get("phone"):
            lines.append(f"📞 {d['phone']}")
        return lines

    # ------------------------------------------------------------ menu screens
    def _model_actions(self, b):
        return [
            {"id": "test_drive", "label": f"🗓️ Book a {self._action_word(b['kind'])}"},
            {"id": "price_quote", "label": "💰 Get on-road price"},
            {"id": "finance", "label": "🏦 EMI / finance options"},
            {"id": "back", "label": f"🔙 See other {b['name']} models"},
        ]

    def render(self, s) -> dict:
        state = s["state"]
        co = self.c["company"]
        if state in ("MAIN", "DONE"):
            return reply(
                f"How can I help you? Please choose an option:\n\n{numbered(self.main_menu)}\n\n"
                '_Reply with a number, or just type what you need, e.g. "service" or "Magnite"._',
                quick_from(self.main_menu),
            )
        if state == "BRAND":
            b = self.brands[s["sel"]["brand_id"]]
            several_groups = len({m["group"] for m in b["models"]}) > 1
            lines, last_group = [], None
            for i, m in enumerate(b["models"]):
                head = f"\n*{m['group']}*\n" if several_groups and m["group"] != last_group else ""
                last_group = m["group"]
                lines.append(f"{head}{num(i + 1)} {m['name']}")
            return reply(
                f"{b['emoji']} *{b['title']}*\nWhich model are you interested in?\n" + "\n".join(lines) + f"\n\n{NAV}",
                [{"reply": str(i + 1), "label": m["name"]} for i, m in enumerate(b["models"])],
            )
        if state == "MODEL":
            b = self.brands[s["sel"]["brand_id"]]
            m = self._model(b["id"], s["sel"]["model_id"])
            acts = self._model_actions(b)
            bullets = "\n".join(f"• {h}" for h in m["highlights"])
            return reply(f"*{m['name']}*\n{bullets}\n\nWhat would you like to do?\n\n{numbered(acts)}\n\n{NAV}", quick_from(acts))
        if state == "SHOWROOM":
            items = self._branch_items()
            return reply(f"📍 *{co['short_name']} showrooms & service centres*\nChoose a city for directions:\n\n{numbered(items)}\n\n{NAV}", quick_from(items))
        if state == "BRANCH":
            br = self.branches[s["sel"]["branch_id"]]
            maps = "https://www.google.com/maps/search/?api=1&query=" + quote(f"Autoveer {br['city']} Haryana")
            acts = [{"label": "🗓️ Book a showroom visit"}, {"label": "📍 See other branches"}]
            text = f"📍 *{co['short_name']}, {br['city']}*" + (f" ({br['note']})" if br.get("note") else "") + "\n"
            if br.get("address"):
                text += f"🏢 {br['address']}\n"
            text += f"📞 {br.get('phone') or co['phone']}\n🗺️ Directions: {maps}\n\n{numbered(acts)}\n\n{NAV}"
            return reply(text, quick_from(acts))
        return reply("")

    # ------------------------------------------------------------ flow machinery
    def _start_flow(self, s, name, data, return_to, ctx, out):
        s["state"] = "FLOW"
        s["flow"] = {"name": name, "step": -1, "data": dict(data), "return_to": return_to}
        phone = normalize_phone(ctx.get("phone"))
        if phone:
            s["flow"]["data"]["phone"] = phone
        self._advance(s, ctx, out, +1)

    def _advance(self, s, ctx, out, direction):
        """Move to the next (+1) or previous (-1) non-skipped step and ask it."""
        steps = self.FLOWS[s["flow"]["name"]]
        i = s["flow"]["step"] + direction
        while 0 <= i < len(steps) and self.fields[steps[i]].skip(s["flow"]["data"], ctx):
            i += direction
        if i < 0:  # backed out of the first question
            back = s["flow"].get("return_to") or {"state": "MAIN", "sel": {}}
            s["flow"] = None
            s["state"] = back["state"]
            s["sel"] = back.get("sel") or {}
            out.append(self.render(s))
            return
        s["flow"]["step"] = i
        field = self.fields[steps[i]]
        if direction < 0:
            s["flow"]["data"].pop(field.key, None)  # re-asking it, so forget the old answer
        out.append(field.ask(s, ctx))

    def _handle_flow(self, s, raw, low, ctx, out):
        steps = self.FLOWS[s["flow"]["name"]]
        field = self.fields[steps[s["flow"]["step"]]]
        if low in ("0", "back"):
            return self._advance(s, ctx, out, -1)
        result = field.parse(raw, low, s, ctx)
        if "error" in result:
            out.append(reply(f"⚠️ {result['error']}"))
            out.append(field.ask(s, ctx))
            return None
        if field.key == "confirmed":
            if not result["ok"]:
                d = s["flow"]["data"]
                keep = {k: d[k] for k in ("brand_id", "model_id", "interest") if d.get(k)}
                if s["flow"]["name"] == "visit":
                    keep["branch_id"] = d["branch_id"]
                name, return_to = s["flow"]["name"], s["flow"]["return_to"]
                out.append(reply("No problem, let us start again. ✏️"))
                return self._start_flow(s, name, keep, return_to, ctx, out)
            return self._finish_flow(s, ctx, out)
        s["flow"]["data"][field.key] = result["ok"]
        return self._advance(s, ctx, out, +1)

    def _finish_flow(self, s, ctx, out) -> dict:
        f = s["flow"]
        d = f["data"]
        model = self._model(d.get("brand_id"), d.get("model_id")) if d.get("model_id") else None
        lead = {
            "ref": self.make_ref(self.now()),
            "lead_type": f["name"],
            "title": self._lead_title(f),
            "interest": d.get("interest", ""),
            "brand": self.brands[d["brand_id"]]["name"] if d.get("brand_id") else "",
            "model_name": model["name"] if model else "",
            "vehicle_type": self._label("vehicle_types", d.get("vehicle_type")) or "",
            "service_type": self._label("service_types", d.get("service_type")) or "",
            "reg_no": d.get("reg_no") or "",
            "topic": d.get("topic", ""),
            "preferred_date": d.get("date"),
            "branch": self.branches[d["branch_id"]]["city"] if d.get("branch_id") else "",
            "name": d.get("name", ""),
            "phone": d.get("phone", ""),
            "whatsapp": (normalize_phone(ctx.get("phone")) or str(ctx.get("phone"))) if ctx.get("phone") else "",
            "channel": ctx.get("channel", "whatsapp"),
        }
        where = f"our *{lead['branch']}* team" if lead["branch"] else "our team"
        out.append(reply(
            f"✅ *Thank you, {d['name']}!* Your request is registered.\n\n"
            f"🎫 Reference no: *{lead['ref']}*\n"
            f"{where[0].upper()}{where[1:]} will call you on *{d['phone']}* shortly to confirm.\n\n"
            f"For anything urgent, call {self.c['company']['phone']}.\n_Reply MENU anytime for more options._",
            [{"reply": "menu", "label": "Main menu"}],
        ))
        s["flow"] = None
        s["state"] = "DONE"
        return lead

    # ------------------------------------------------------------ routing
    def _go(self, s, target, ctx, out):
        kind, _, rest = target.partition(":")
        if kind == "brand":
            s.update(state="BRAND", sel={"brand_id": rest})
            out.append(self.render(s))
        elif kind == "model":
            brand_id, _, model_id = rest.partition(":")
            s.update(state="MODEL", sel={"brand_id": brand_id, "model_id": model_id})
            out.append(self.render(s))
        elif kind == "service":
            # "my tractor needs service" -> brand already known, skip that question
            self._start_flow(s, "service", {"brand_id": rest} if rest else {}, {"state": "MAIN", "sel": {}}, ctx, out)
        elif kind == "insurance":
            self._start_flow(s, "insurance", {}, {"state": "MAIN", "sel": {}}, ctx, out)
        elif kind == "executive":
            back_state = "MAIN" if s["state"] == "FLOW" else s["state"]
            self._start_flow(s, "callback", {}, {"state": back_state, "sel": s["sel"]}, ctx, out)
        elif kind == "showroom":
            s.update(state="SHOWROOM", sel={})
            out.append(self.render(s))
        elif kind == "about":
            co = self.c["company"]
            s.update(state="MAIN", sel={})
            out.append(reply(f"ℹ️ *About {co['name']}*\n\n{co['about']}\n\n🌐 {co['website']}\n📞 {co['phone']}\n🏢 {co['hq']}"))
            out.append(self.render(s))
        else:
            s.update(state="MAIN", sel={})
            out.append(self.render(s))

    def match_keyword(self, low: str) -> Optional[str]:
        words = [w for w in re.split(r"[^a-z0-9]+", low) if w]
        padded = f" {' '.join(words)} "
        hits = lambda kws: any(f" {k} " in padded for k in kws)  # noqa: E731
        kw = self.c["keywords"]
        # 1) intents ("magnite service" -> service), 2) a specific model, 3) a brand
        for target, kws in kw.items():
            if target not in self.brands and hits(kws):
                if target != "service":
                    return target
                brand = next((bid for bid, k in kw.items() if bid in self.brands and hits(k)), None)
                return f"service:{brand}" if brand else "service"
        scores = {}
        for tok, brand_id, model_id in self.model_index:
            if tok in words:
                scores[(brand_id, model_id)] = scores.get((brand_id, model_id), 0) + 1
        if scores:
            brand_id, model_id = max(scores, key=scores.get)
            return f"model:{brand_id}:{model_id}"
        for target, kws in kw.items():
            if target in self.brands and hits(kws):
                return f"brand:{target}"
        return None

    def _route_menu(self, s, low, ctx, out):
        state, sel = s["state"], s["sel"]
        if low in ("0", "back"):
            if state == "MODEL":
                return self._go(s, f"brand:{sel['brand_id']}", ctx, out)
            if state == "BRANCH":
                return self._go(s, "showroom", ctx, out)
            return self._go(s, "main", ctx, out)
        if state in ("MAIN", "DONE"):
            n = pick_number(low, len(self.main_menu))
            if n:
                return self._go(s, self.main_menu[n - 1]["id"], ctx, out)
        elif state == "BRAND":
            b = self.brands[sel["brand_id"]]
            n = pick_number(low, len(b["models"]))
            if n:
                return self._go(s, f"model:{b['id']}:{b['models'][n - 1]['id']}", ctx, out)
        elif state == "MODEL":
            b = self.brands[sel["brand_id"]]
            acts = self._model_actions(b)
            n = pick_number(low, len(acts))
            if n:
                action = acts[n - 1]["id"]
                if action == "back":
                    return self._go(s, f"brand:{b['id']}", ctx, out)
                data = {"brand_id": b["id"], "model_id": sel["model_id"], "interest": action}
                return self._start_flow(s, "sales", data, {"state": "MODEL", "sel": dict(sel)}, ctx, out)
        elif state == "SHOWROOM":
            n = pick_number(low, len(self.c["branches"]))
            if n:
                s.update(state="BRANCH", sel={"branch_id": self.c["branches"][n - 1]["id"]})
                return out.append(self.render(s))
        elif state == "BRANCH":
            n = pick_number(low, 2)
            if n == 1:
                return self._start_flow(s, "visit", {"branch_id": sel["branch_id"]}, {"state": "BRANCH", "sel": dict(sel)}, ctx, out)
            if n == 2:
                return self._go(s, "showroom", ctx, out)
        target = self.match_keyword(low)
        if target:
            return self._go(s, target, ctx, out)
        out.append(reply("🙏 Sorry, I didn't get that. Please reply with one of the numbers below."))
        out.append(self.render(s))

    # ------------------------------------------------------------ main entry
    def handle(self, prev: Optional[dict], raw, ctx: Optional[dict] = None) -> dict:
        """Process one incoming message. Returns {"session", "replies", "lead"}."""
        ctx = ctx or {}
        t = self.now()
        text = str(raw if raw is not None else "").strip()
        low = re.sub(r"[!?.,]+$", "", re.sub(r"\s+", " ", text.lower()))
        out, lead = [], None

        expired = not prev or t - datetime.fromisoformat(prev["last_at"]) > self.timeout
        s = self.new_session(t) if expired else _deepcopy(prev)

        if expired:
            co = self.c["company"]
            pn = clean_name(ctx.get("push_name"))
            names = [b["name"] for b in self.c["brands"]]
            brand_list = ", ".join(names[:-1]) + " & " + names[-1]
            out.append(reply(
                f"Namaste{' ' + pn.split(' ')[0] if pn else ''}! 🙏\nWelcome to *{co['short_name']}*, authorised dealer for "
                f"{brand_list} in {co['region']}.\n\nI am the {co['short_name']} virtual assistant. 🤖"
            ))
            target = None if low in RESET_WORDS else self.match_keyword(low)
            self._go(s, target or "main", ctx, out)
        elif low in RESET_WORDS:
            self._go(s, "main", ctx, out)
        elif low in CANCEL_WORDS and s["state"] == "FLOW":
            out.append(reply("Okay, cancelled. 👍"))
            s["flow"] = None
            self._go(s, "main", ctx, out)
        elif s["state"] == "FLOW":
            lead = self._handle_flow(s, text, low, ctx, out)
        elif not text:
            out.append(reply("🙏 I can read text messages only. Please reply with a number from the menu."))
            out.append(self.render(s))
        elif low in THANKS_WORDS and s["state"] in ("DONE", "MAIN"):
            out.append(reply("You're welcome! 🙏 Have a great day.\n_Reply MENU anytime if you need anything else._",
                             [{"reply": "menu", "label": "Main menu"}]))
        else:
            self._route_menu(s, low, ctx, out)

        s["last_at"] = t.isoformat()
        return {"session": s, "replies": [r for r in out if r and r.get("text")], "lead": lead}


def _deepcopy(obj):
    return copy.deepcopy(obj)
