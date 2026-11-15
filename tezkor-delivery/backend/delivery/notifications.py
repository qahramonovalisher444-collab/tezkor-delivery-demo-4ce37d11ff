from datetime import timedelta
import uuid
from urllib.error import URLError

from django.conf import settings
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from .models import Order, OrderNotification
from .telegram import TelegramAPIError, bot_request


MAX_ATTEMPTS = 5
LEASE_SECONDS = 120


def enqueue_order_notification(event):
    order = event.order
    if not order.customer.telegram_id:
        return None
    notification, _ = OrderNotification.objects.get_or_create(event=event, defaults={
        "chat_id": order.customer.telegram_id,
        "text": f"Tezkor • Buyurtma #{order.id}\nHolat: {Order.Status(event.status).label}\nJami: {order.total:,.0f} so‘m",
    })
    return notification


def notification_queryset():
    newer = OrderNotification.objects.filter(event__order_id=OuterRef("event__order_id"), event_id__gt=OuterRef("event_id"))
    return OrderNotification.objects.select_related("event", "event__order", "event__order__customer").annotate(has_newer=Exists(newer))


def claim_notification():
    for attempt in range(20):
        now = timezone.now()
        if OrderNotification.objects.filter(retry_after_until__gt=now).exists():
            return None
        due = Q(status=OrderNotification.Status.PENDING, next_attempt_at__lte=now) | Q(status=OrderNotification.Status.PROCESSING, locked_at__lt=now - timedelta(seconds=LEASE_SECONDS))
        earlier = OrderNotification.objects.filter(event__order_id=OuterRef("event__order_id"), event_id__lt=OuterRef("event_id"), status__in=[OrderNotification.Status.PENDING, OrderNotification.Status.PROCESSING])
        candidate = OrderNotification.objects.filter(due).annotate(has_earlier=Exists(earlier)).filter(has_earlier=False).order_by("event_id").first()
        if candidate is None:
            return None
        if candidate.attempts >= MAX_ATTEMPTS:
            OrderNotification.objects.filter(pk=candidate.pk).filter(due).update(status=OrderNotification.Status.FAILED, locked_at=None, lock_token=None, last_error="Qayta urinishlar limiti tugadi.", updated_at=now)
            continue
        token = uuid.uuid4()
        claimed = OrderNotification.objects.filter(pk=candidate.pk).filter(due).update(status=OrderNotification.Status.PROCESSING, lock_token=token, locked_at=now, attempts=F("attempts") + 1, updated_at=now)
        if claimed:
            return OrderNotification.objects.get(pk=candidate.pk, lock_token=token)
    return None


def finish_notification(notification, *, error="", permanent=False, retry_after=None, rate_limited=False, message_id=None):
    now = timezone.now()
    values = {"locked_at": None, "lock_token": None, "updated_at": now, "last_error": error}
    delay = max(min(15 * 2 ** (notification.attempts - 1), 900), min(retry_after or 0, 86400))
    if rate_limited:
        values["retry_after_until"] = now + timedelta(seconds=delay)
    if not error:
        values.update(status=OrderNotification.Status.SENT, message_id=message_id, sent_at=now)
    elif permanent or notification.attempts >= MAX_ATTEMPTS:
        values["status"] = OrderNotification.Status.FAILED
    else:
        values.update(status=OrderNotification.Status.PENDING, next_attempt_at=now + timedelta(seconds=delay))
    return OrderNotification.objects.filter(pk=notification.pk, status=OrderNotification.Status.PROCESSING, lock_token=notification.lock_token).update(**values)


def deliver_notification(notification):
    if not settings.BOT_TOKEN:
        finish_notification(notification, error="Telegram bot tokeni sozlanmagan.", permanent=True)
        return
    try:
        result = bot_request("sendMessage", {"chat_id": notification.chat_id, "text": notification.text}, timeout=10)
        if not isinstance(result, dict) or type(result.get("message_id")) is not int or not 0 < result["message_id"] < 2**63:
            raise RuntimeError("Invalid message response")
    except TelegramAPIError as error:
        messages = {400: "Telegram xabarni qabul qilmadi.", 401: "Telegram bot tokeni yaroqsiz.", 403: "Botga xabar yuborish taqiqlangan yoki foydalanuvchi botni bloklagan.", 404: "Telegram bot topilmadi.", 429: "Telegram yuborish limitiga yetildi. Keyinroq qayta uriniladi."}
        finish_notification(notification, error=messages.get(error.code, f"Telegram API xatosi ({error.code})."), permanent=error.code in {400, 401, 403, 404}, retry_after=error.retry_after, rate_limited=error.code == 429)
    except (URLError, TimeoutError, OSError):
        finish_notification(notification, error="Telegram tarmog‘iga ulanib bo‘lmadi. Qayta uriniladi.")
    except (RuntimeError, ValueError, KeyError):
        finish_notification(notification, error="Telegram javobini tekshirib bo‘lmadi. Qayta uriniladi.")
    else:
        finish_notification(notification, message_id=result["message_id"])


def process_due_notifications(limit=20):
    processed = 0
    for attempt in range(limit):
        notification = claim_notification()
        if notification is None:
            break
        deliver_notification(notification)
        processed += 1
    return processed
