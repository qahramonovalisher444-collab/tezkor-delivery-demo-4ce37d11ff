from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Order, OrderNotification
from .notifications import MAX_ATTEMPTS, notification_queryset
from .permissions import IsDeliveryAdmin


class NotificationSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="event.order_id", read_only=True)
    order_status = serializers.CharField(source="event.status", read_only=True)
    order_status_label = serializers.CharField(source="event.get_status_display", read_only=True)
    customer_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    can_retry = serializers.SerializerMethodField()

    class Meta:
        model = OrderNotification
        fields = ["id", "order_id", "order_status", "order_status_label", "customer_name", "status", "status_label", "attempts", "next_attempt_at", "last_error", "sent_at", "created_at", "can_retry", "text"]

    def get_customer_name(self, notification):
        user = notification.event.order.customer
        return user.get_full_name() or user.username

    def get_can_retry(self, notification):
        return bool(settings.BOT_TOKEN and notification.status == OrderNotification.Status.FAILED and not notification.has_newer)


class NotificationFilters(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderNotification.Status.choices, required=False)
    order_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1, required=False)


class NotificationPagination(PageNumberPagination):
    page_size = 25


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsDeliveryAdmin]
    pagination_class = NotificationPagination

    def get_queryset(self):
        notifications = notification_queryset()
        if self.action != "list":
            return notifications
        serializer = NotificationFilters(data=self.request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data
        if filters.get("status"):
            notifications = notifications.filter(status=filters["status"])
        if filters.get("order_id"):
            notifications = notifications.filter(event__order_id=filters["order_id"])
        return notifications

    @action(detail=False, methods=["get"])
    def summary(self, request):
        counts = {value: 0 for value in OrderNotification.Status.values}
        counts.update({row["status"]: row["count"] for row in OrderNotification.objects.values("status").annotate(count=Count("id"))})
        paused_until = OrderNotification.objects.filter(retry_after_until__gt=timezone.now()).aggregate(value=Max("retry_after_until"))["value"]
        return Response({"counts": counts, "total": sum(counts.values()), "bot_configured": bool(settings.BOT_TOKEN), "max_attempts": MAX_ATTEMPTS, "paused_until": paused_until})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def retry(self, request, pk=None):
        visible = self.get_object()
        Order.objects.select_for_update().get(pk=visible.event.order_id)
        notification = get_object_or_404(OrderNotification.objects.select_for_update(), pk=visible.pk)
        if not settings.BOT_TOKEN:
            raise ValidationError("Avval Telegram bot tokenini sozlang.")
        if notification.status != OrderNotification.Status.FAILED:
            raise ValidationError("Faqat xato bilan tugagan xabarnomani qayta yuborish mumkin.")
        if OrderNotification.objects.filter(event__order_id=visible.event.order_id, event_id__gt=notification.event_id).exists():
            raise ValidationError("Buyurtmaning keyingi holat xabari bor. Eskirgan xabar qayta yuborilmaydi.")
        notification.status = OrderNotification.Status.PENDING
        notification.attempts = 0
        notification.last_error = ""
        notification.next_attempt_at = timezone.now()
        notification.lock_token = None
        notification.locked_at = None
        notification.save(update_fields=["status", "attempts", "last_error", "next_attempt_at", "lock_token", "locked_at", "updated_at"])
        return Response(self.get_serializer(self.get_queryset().get(pk=notification.pk)).data)
