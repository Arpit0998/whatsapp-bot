from django.db import models


class ChatSession(models.Model):
    """Where each customer is in the conversation (engine state as JSON)."""

    user_id = models.CharField(max_length=64, unique=True, help_text="WhatsApp number, or web:/cli: id for the demo channels")
    channel = models.CharField(max_length=16, default="whatsapp")
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user_id} ({self.data.get('state', '?')})"


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        BOOKED = "booked", "Booked / Converted"
        LOST = "lost", "Not interested"

    class Type(models.TextChoices):
        SALES = "sales", "Sales enquiry"
        SERVICE = "service", "Service booking"
        INSURANCE = "insurance", "Insurance / finance"
        CALLBACK = "callback", "Callback"
        VISIT = "visit", "Showroom visit"

    ref = models.CharField("Reference", max_length=20, unique=True)
    lead_type = models.CharField(max_length=16, choices=Type.choices)
    title = models.CharField(max_length=60)
    interest = models.CharField(max_length=20, blank=True)
    brand = models.CharField(max_length=40, blank=True)
    model_name = models.CharField("Model", max_length=60, blank=True)
    vehicle_type = models.CharField(max_length=40, blank=True)
    service_type = models.CharField(max_length=60, blank=True)
    reg_no = models.CharField("Reg. no.", max_length=20, blank=True)
    topic = models.TextField("Message", blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    branch = models.CharField(max_length=40, blank=True)
    name = models.CharField(max_length=60)
    phone = models.CharField(max_length=15)
    whatsapp = models.CharField(max_length=20, blank=True)
    channel = models.CharField(max_length=16, default="whatsapp")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    notes = models.TextField(blank=True, help_text="Internal notes for the sales / service team")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ref} · {self.title} · {self.name}"

    def as_engine_dict(self) -> dict:
        return {f: getattr(self, f) for f in ("ref", "title", "brand", "model_name", "vehicle_type", "service_type",
                                               "reg_no", "topic", "branch", "name", "phone", "whatsapp")} | {
            "preferred_date": self.preferred_date.isoformat() if self.preferred_date else None}


class Message(models.Model):
    """Every message in and out: an audit trail, and de-duplication of webhook retries."""

    class Direction(models.TextChoices):
        IN = "in", "Customer → bot"
        OUT = "out", "Bot → customer"

    user_id = models.CharField(max_length=64, db_index=True)
    channel = models.CharField(max_length=16, default="whatsapp")
    direction = models.CharField(max_length=3, choices=Direction.choices)
    text = models.TextField(blank=True)
    wa_message_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_direction_display()} {self.user_id}: {self.text[:40]}"
