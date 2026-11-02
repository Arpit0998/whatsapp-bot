import json
import logging

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from . import services, whatsapp
from .engine import normalize_phone

log = logging.getLogger(__name__)

@csrf_exempt  
@require_http_methods(["GET", "POST"])
def webhook(request):
    if request.method == "GET":
        
        if request.GET.get("hub.mode") == "subscribe" and request.GET.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
        return HttpResponseForbidden("verification failed")

    if not whatsapp.verify_signature(request.body, request.headers.get("X-Hub-Signature-256", "")):
        return HttpResponseForbidden("bad signature")
    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)

    for msg in whatsapp.extract_messages(payload):
        if services.already_processed(msg["id"]):
            continue
        try:
            result = services.process_message(
                msg["from"], msg["text"], channel="whatsapp",
                phone=normalize_phone(msg["from"]) or msg["from"], push_name=msg["name"], wa_message_id=msg["id"],
            )
        except IntegrityError: 
            continue
        except Exception:  
            log.exception("failed to process message %s", msg["id"])
            continue
        whatsapp.mark_read(msg["id"])
        for r in result.replies:
            whatsapp.send_text(msg["from"], r["text"])
        if result.staff_message:
            services.alert_staff(result.staff_message)

    return HttpResponse("ok")  
@ensure_csrf_cookie
def demo(request):
    return render(request, "bot/demo.html", {"whatsapp_live": whatsapp.is_configured()})


def _web_user(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return f"web:{request.session.session_key}"


@require_POST
def api_chat(request):
    try:
        text = str(json.loads(request.body).get("text", ""))[:1000]
    except ValueError:
        return JsonResponse({"error": "invalid JSON"}, status=400)
    result = services.process_message(_web_user(request), text, channel="web")
    lead = None
    if result.lead:
        lead = result.lead.as_engine_dict() | {"id": result.lead.pk}
    return JsonResponse({"replies": result.replies, "lead": lead, "staff_message": result.staff_message})


@require_POST
def api_reset(request):
    services.reset_session(_web_user(request))
    return JsonResponse({"ok": True})
