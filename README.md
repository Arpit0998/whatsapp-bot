# Autoveer WhatsApp Assistant (Python / Django)

A rule-based WhatsApp chatbot for **Autoveer Pvt Ltd** ([autoveer.com](https://autoveer.com)). Autoveer is an authorised multi-brand dealer in Haryana for **Nissan, Bajaj, Ashok Leyland and Massey Ferguson**, with 8 branches.

It is built on **Django**. Customers message the dealership's WhatsApp number, and the bot answers 24×7:

- shows models
- books test drives, demos and services
- handles insurance and finance enquiries
- gives showroom directions

Every confirmed request becomes a **Lead** in the database with a reference number. Leads are managed in **Django Admin** (status, notes, filters, CSV export), and the branch team gets an instant WhatsApp alert.

---

## Features

| Menu | Flow | Lead captured |
|---|---|---|
| 🚗 Nissan / 🏍️ Bajaj / 🚚 Ashok Leyland / 🚜 Massey Ferguson | Brand → model (highlights) → **Test Drive / Test Ride / Demo**, **On-road price** or **EMI** | name, phone, branch, date (test drive only) |
| 🔧 Book a Service | brand → reg. no. (validated, can skip) → service type → date → branch | full job card |
| 🛡️ Insurance & Finance | new / renewal / claim / loan → vehicle type → reg. no. | enquiry |
| 📍 Showrooms & Directions | 8 cities → Google Maps link → *book a showroom visit* | visit booking |
| 👤 Talk to an Executive | free-text topic → name → phone | callback request |

- **Understands free text.** "magnite price", "my tractor needs service" (Massey Ferguson is pre-selected), "car insurance" and "showroom kahan hai" all work.
- **Validation.** It checks Indian mobile numbers, registration numbers (including BH series), and dates. It rejects past dates, impossible dates (31/02), and dates more than 90 days ahead.
- **Uses the customer's WhatsApp number and profile name**, so the customer doesn't have to retype them.
- `0` goes back, `MENU` returns to the main menu, and `cancel` exits a form. Sessions expire after 30 minutes.
- **Django Admin.** The lead list has inline status (New → Contacted → Booked / Lost), notes, filters by branch, brand, type and date, search, and a CSV export action. Admin also has a full message log and the live chat sessions.
- **Webhook hardening.** Every request's HMAC signature (`X-Hub-Signature-256`) is checked. Meta's retries are de-duplicated by message id. The webhook always answers 200 quickly. Status callbacks and reactions are ignored.

## Architecture

```
Customer ─► WhatsApp ─► Meta Cloud API ──POST /webhook/──► bot/views.py ──┐
Browser demo (/) ──────────────────────POST /api/chat/──► bot/views.py ──┤
Terminal: manage.py chat ─────────────────────────────────────────────────┤
                                                                           ▼
                                                    bot/services.py  (DB transaction)
                                                      │  load ChatSession → engine → save
                                                      ▼
                                bot/engine.py   pure state machine, no Django imports
                                bot/content.py  brands, models, branches, keywords
                                                      │
                     Lead / Message / ChatSession ◄───┤
                     (SQLite, Django Admin)           └──► staff alert via Cloud API
```

- `engine.py` is a pure class: `handle(session, text, ctx) → {session, replies, lead}`. It has no database and no HTTP, so it is fully unit-tested with a fixed clock.
- Forms are declarative. Each flow is a list of fields, and each field has its own prompt, parser, validator and skip rule.
- `services.py` locks the user's session row (`select_for_update`) so two quick messages from the same customer are processed in order.

## Run it locally

Requires **Python 3.11+**.

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # for /admin
python manage.py test bot         # 26 tests
python manage.py runserver
```

- **http://127.0.0.1:8000/** is the WhatsApp-style web demo. It talks to the real Django backend.
- **http://127.0.0.1:8000/admin/** is the leads dashboard.
- `python manage.py chat --phone 9876543210 --name "Rahul"` lets you chat in the terminal.

## Connect real WhatsApp (Cloud API)

1. Go to [developers.facebook.com](https://developers.facebook.com) → **Create app** → type *Business* → add **WhatsApp**.
2. On **WhatsApp → API Setup**, note the **temporary access token** and the **Phone number ID**, and add your own number as a test recipient.
3. `copy .env.example .env` and fill in `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_APP_SECRET` (*App settings → Basic*). Put your own number in `STAFF_NUMBERS`.
4. Expose your local server: `ngrok http 8000`.
5. Go to **WhatsApp → Configuration → Webhook**:
   - Callback URL: `https://<your-ngrok>.ngrok-free.app/webhook/`
   - Verify token: the same value as `WHATSAPP_VERIFY_TOKEN`
   - Click **Verify and save**, then subscribe to the **messages** field.
6. Send "hi" from your phone to the test number.

## Production notes / next steps

- **Background sending.** Replies are sent inside the webhook request, which is fine at dealership volume. At scale, push sending to Celery or RQ so the webhook returns in milliseconds.
- **Interactive messages.** The Cloud API supports list menus and reply buttons. The engine already returns `quick` replies per message, so `whatsapp.py` can turn them into buttons.
- **Template messages.** Use them for service-due reminders and follow-ups after the 24-hour customer-service window.
- **Per-branch routing.** Add a phone per branch in `content.py` to alert only that branch's team.
- **Postgres + gunicorn** for deployment. `DATABASES` and the secrets already come from the environment.

## Project layout

```
autoveer_site/settings.py   config (reads .env), WhatsApp settings
bot/content.py              catalogue, branches, keywords (edit to change content)
bot/engine.py               conversation state machine + validators
bot/services.py             engine <-> database glue, staff alerts
bot/whatsapp.py             Cloud API: signature check, payload parsing, send
bot/views.py                /webhook/, web demo, /api/chat/
bot/models.py               Lead, ChatSession, Message
bot/admin.py                leads dashboard, CSV export
bot/templates/bot/demo.html WhatsApp-style chat UI
bot/management/commands/chat.py   terminal simulator
bot/tests/                  engine + webhook/API tests
```
