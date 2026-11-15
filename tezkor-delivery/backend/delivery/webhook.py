import hmac
import json

from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .bot_updates import welcome_message
from .models import TelegramWebhookUpdate
from .telegram import bot_request


@csrf_exempt
@require_POST
def telegram_webhook(request):
    if not getattr(settings, "TELEGRAM_WEBHOOK_ENABLED", False):
        return JsonResponse({"detail": "Not found"}, status=404)
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secret or not hmac.compare_digest(secret.encode(), received.encode()):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.content_type != "application/json":
        return JsonResponse({"detail": "JSON required"}, status=415)
    try:
        if len(request.body) > 131072:
            raise ValueError
        update = json.loads(request.body)
        if not isinstance(update, dict) or type(update.get("update_id")) is not int or not 0 <= update["update_id"] < 2**63:
            raise ValueError
    except (ValueError, UnicodeError):
        return JsonResponse({"detail": "Invalid update"}, status=400)
    try:
        with transaction.atomic():
            _, created = TelegramWebhookUpdate.objects.get_or_create(update_id=update["update_id"])
            if created:
                payload = welcome_message(update)
                if payload:
                    bot_request("sendMessage", payload, timeout=8)
    except (DatabaseError, RuntimeError, OSError, ValueError):
        # Telegram retries non-2xx responses. Roll back the receipt so a retry can run.
        return JsonResponse({"detail": "Retry later"}, status=503)
    return JsonResponse({"ok": True})
