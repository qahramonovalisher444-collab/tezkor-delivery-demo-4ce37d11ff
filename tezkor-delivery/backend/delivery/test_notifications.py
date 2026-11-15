from datetime import timedelta
from io import BytesIO, StringIO
from http.client import IncompleteRead
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import uuid

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Category, Order, OrderEvent, OrderNotification, Product, User
from .notifications import MAX_ATTEMPTS, claim_notification, enqueue_order_notification, finish_notification, process_due_notifications
from .telegram import TelegramAPIError, bot_request


@override_settings(BOT_TOKEN="test-token-only")
class NotificationTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="buyer", telegram_id=123456789)
        self.admin_user = User.objects.create_user(username="manager", role="admin")
        self.order = Order.objects.create(customer=self.customer, address="Toshkent, Navoiy 12", phone="+998901234567", subtotal=35000, delivery_fee=10000, total=45000)
        self.event = OrderEvent.objects.create(order=self.order, status="pending", actor=self.customer)
        self.client.force_authenticate(self.admin_user)

    def queue(self):
        return enqueue_order_notification(self.event)

    def test_event_is_enqueued_once_without_sending(self):
        with patch("delivery.notifications.bot_request") as sender:
            first = self.queue()
            second = self.queue()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(OrderNotification.objects.count(), 1)
        sender.assert_not_called()

    @override_settings(BOT_TOKEN="")
    def test_missing_token_keeps_durable_record_and_can_be_retried_after_configuration(self):
        notification = self.queue()
        with patch("delivery.notifications.bot_request") as sender:
            self.assertEqual(process_due_notifications(), 1)
        sender.assert_not_called()
        notification.refresh_from_db()
        self.assertEqual(notification.status, "failed")
        self.assertEqual(self.client.post(f"/api/notifications/{notification.pk}/retry/").status_code, 400)
        with override_settings(BOT_TOKEN="configured-test-token"):
            response = self.client.post(f"/api/notifications/{notification.pk}/retry/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["attempts"], 0)

    def test_demo_customer_without_telegram_has_no_notification(self):
        self.customer.telegram_id = None
        self.customer.save(update_fields=["telegram_id"])
        self.assertIsNone(self.queue())
        self.assertEqual(OrderNotification.objects.count(), 0)

    def test_snapshot_keeps_original_status_and_total(self):
        notification = self.queue()
        self.order.status = "delivered"
        self.order.total = 90000
        self.order.save()
        notification.refresh_from_db()
        self.assertIn("Holat: Yangi", notification.text)
        self.assertIn("45,000", notification.text)
        self.assertNotIn("90,000", notification.text)

    def test_transaction_rollback_removes_queued_notification(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.queue()
                raise RuntimeError("Rollback")
        self.assertEqual(OrderNotification.objects.count(), 0)

    def test_status_and_history_roll_back_when_enqueue_fails(self):
        with patch("delivery.views.enqueue_order_notification", side_effect=RuntimeError("storage failed")):
            with self.assertRaises(RuntimeError):
                self.client.post(f"/api/orders/{self.order.pk}/status/", {"status": "confirmed"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")
        self.assertEqual(self.order.events.count(), 1)

    def test_new_order_is_not_committed_if_its_notification_cannot_be_saved(self):
        category = Category.objects.create(name="Burgerlar")
        product = Product.objects.create(name="Burger", category=category, price=35000)
        self.client.force_authenticate(self.customer)
        with patch("delivery.serializers.enqueue_order_notification", side_effect=RuntimeError("storage failed")):
            with self.assertRaises(RuntimeError):
                self.client.post("/api/orders/", {"items": [{"product": product.pk, "quantity": 1}], "address": "Toshkent, Bobur 12", "phone": "+998901234567", "save_details": True})
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderEvent.objects.count(), 1)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "")

    def test_success_is_recorded_and_not_sent_again(self):
        notification = self.queue()
        with patch("delivery.notifications.bot_request", return_value={"message_id": 100}) as sender:
            self.assertEqual(process_due_notifications(), 1)
            self.assertEqual(process_due_notifications(), 0)
        sender.assert_called_once_with("sendMessage", {"chat_id": 123456789, "text": notification.text}, timeout=10)
        notification.refresh_from_db()
        self.assertEqual(notification.status, "sent")
        self.assertEqual(notification.message_id, 100)
        self.assertIsNotNone(notification.sent_at)
        self.assertIsNone(notification.lock_token)

    def test_network_error_retries_later_without_losing_record(self):
        notification = self.queue()
        now = timezone.now()
        with patch("delivery.notifications.bot_request", side_effect=URLError("a-url-containing-a-secret")):
            self.assertEqual(process_due_notifications(), 1)
        notification.refresh_from_db()
        self.assertEqual(notification.status, "pending")
        self.assertEqual(notification.attempts, 1)
        self.assertGreaterEqual(notification.next_attempt_at, now + timedelta(seconds=15))
        self.assertNotIn("secret", notification.last_error)
        with patch("delivery.notifications.bot_request") as sender:
            self.assertEqual(process_due_notifications(), 0)
        sender.assert_not_called()
        OrderNotification.objects.filter(pk=notification.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        with patch("delivery.notifications.bot_request", return_value={"message_id": 101}):
            self.assertEqual(process_due_notifications(), 1)
        notification.refresh_from_db()
        self.assertEqual(notification.status, "sent")
        self.assertEqual(notification.attempts, 2)

    def test_telegram_429_pauses_other_notifications_and_honors_retry_after(self):
        first = self.queue()
        other_order = Order.objects.create(customer=self.customer, address="Toshkent, Bobur 12", phone="+998901234567", subtotal=35000, delivery_fee=10000, total=45000)
        other_event = OrderEvent.objects.create(order=other_order, status="pending", actor=self.customer)
        second = enqueue_order_notification(other_event)
        before = timezone.now()
        with patch("delivery.notifications.bot_request", side_effect=TelegramAPIError(429, 90)) as sender:
            self.assertEqual(process_due_notifications(), 1)
        sender.assert_called_once()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertGreaterEqual(first.retry_after_until, before + timedelta(seconds=90))
        self.assertEqual(second.attempts, 0)
        summary = self.client.get("/api/notifications/summary/").data
        self.assertIsNotNone(summary["paused_until"])

    def test_manual_retry_cannot_bypass_telegram_cooldown(self):
        notification = self.queue()
        OrderNotification.objects.filter(pk=notification.pk).update(attempts=MAX_ATTEMPTS - 1)
        with patch("delivery.notifications.bot_request", side_effect=TelegramAPIError(429, 90)):
            process_due_notifications()
        self.assertEqual(self.client.post(f"/api/notifications/{notification.pk}/retry/").status_code, 200)
        with patch("delivery.notifications.bot_request") as sender:
            self.assertEqual(process_due_notifications(), 0)
        sender.assert_not_called()

    def test_invalid_delivery_response_is_not_marked_sent(self):
        notification = self.queue()
        with patch("delivery.notifications.bot_request", return_value={"message_id": "invalid"}):
            process_due_notifications()
        notification.refresh_from_db()
        self.assertEqual(notification.status, "pending")
        self.assertIsNone(notification.sent_at)

    def test_permanent_error_stops_and_does_not_expose_api_details(self):
        notification = self.queue()
        with patch("delivery.notifications.bot_request", side_effect=TelegramAPIError(403)):
            self.assertEqual(process_due_notifications(), 1)
        notification.refresh_from_db()
        self.assertEqual(notification.status, "failed")
        self.assertIsNone(notification.lock_token)
        self.assertIn("bloklagan", notification.last_error)
        with patch("delivery.notifications.bot_request") as sender:
            self.assertEqual(process_due_notifications(), 0)
        sender.assert_not_called()

    def test_attempt_limit_stops_retries(self):
        notification = self.queue()
        OrderNotification.objects.filter(pk=notification.pk).update(attempts=MAX_ATTEMPTS - 1)
        with patch("delivery.notifications.bot_request", side_effect=TimeoutError()):
            self.assertEqual(process_due_notifications(), 1)
        notification.refresh_from_db()
        self.assertEqual(notification.status, "failed")
        self.assertEqual(notification.attempts, MAX_ATTEMPTS)

    def test_failed_lease_at_limit_is_closed_without_another_send(self):
        notification = self.queue()
        OrderNotification.objects.filter(pk=notification.pk).update(status="processing", attempts=MAX_ATTEMPTS, locked_at=timezone.now() - timedelta(minutes=3), lock_token=uuid.uuid4())
        with patch("delivery.notifications.bot_request") as sender:
            self.assertEqual(process_due_notifications(), 0)
        notification.refresh_from_db()
        self.assertEqual(notification.status, "failed")
        sender.assert_not_called()

    def test_active_lease_is_not_claimed_twice_and_expired_lease_is_recovered(self):
        notification = self.queue()
        first = claim_notification()
        self.assertIsNotNone(first)
        self.assertIsNone(claim_notification())
        OrderNotification.objects.filter(pk=notification.pk).update(locked_at=timezone.now() - timedelta(minutes=3))
        second = claim_notification()
        self.assertNotEqual(first.lock_token, second.lock_token)
        self.assertEqual(finish_notification(first, message_id=1), 0)
        self.assertEqual(finish_notification(second, message_id=2), 1)
        notification.refresh_from_db()
        self.assertEqual(notification.message_id, 2)

    def test_later_order_status_waits_for_earlier_retry(self):
        first = self.queue()
        event = OrderEvent.objects.create(order=self.order, status="confirmed", actor=self.admin_user)
        second = enqueue_order_notification(event)
        with patch("delivery.notifications.bot_request", side_effect=TimeoutError()) as sender:
            self.assertEqual(process_due_notifications(), 1)
        sender.assert_called_once()
        second.refresh_from_db()
        self.assertEqual(second.attempts, 0)
        OrderNotification.objects.filter(pk=first.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        with patch("delivery.notifications.bot_request", side_effect=[{"message_id": 1}, {"message_id": 2}]) as sender:
            self.assertEqual(process_due_notifications(), 2)
        self.assertEqual([call.args[1]["text"] for call in sender.call_args_list], [first.text, second.text])

    def test_only_admin_can_read_or_retry_notifications(self):
        notification = self.queue()
        self.client.force_authenticate(self.customer)
        for endpoint in ["/api/notifications/", "/api/notifications/summary/", f"/api/notifications/{notification.pk}/"]:
            self.assertEqual(self.client.get(endpoint).status_code, 403)
        self.assertEqual(self.client.post(f"/api/notifications/{notification.pk}/retry/").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/notifications/").status_code, 401)

    def test_admin_retry_only_accepts_latest_failed_notification(self):
        first = self.queue()
        OrderNotification.objects.filter(pk=first.pk).update(status="failed", attempts=5, last_error="Failure")
        event = OrderEvent.objects.create(order=self.order, status="confirmed", actor=self.admin_user)
        latest = enqueue_order_notification(event)
        self.assertEqual(self.client.post(f"/api/notifications/{first.pk}/retry/").status_code, 400)
        self.assertEqual(self.client.post(f"/api/notifications/{latest.pk}/retry/").status_code, 400)
        OrderNotification.objects.filter(pk=latest.pk).update(status="failed", attempts=5, last_error="Failure")
        response = self.client.post(f"/api/notifications/{latest.pk}/retry/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["attempts"], 0)
        self.assertEqual(response.data["last_error"], "")
        self.assertFalse(response.data["can_retry"])

    def test_list_filters_and_summary_are_bounded_and_do_not_expose_secrets(self):
        notification = self.queue()
        response = self.client.get("/api/notifications/", {"order_id": self.order.pk, "status": "pending"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], notification.pk)
        self.assertNotIn("chat_id", response.data["results"][0])
        summary = self.client.get("/api/notifications/summary/").data
        self.assertEqual(summary["counts"]["pending"], 1)
        self.assertTrue(summary["bot_configured"])
        self.assertNotIn("test-token-only", json.dumps(summary))
        self.assertEqual(self.client.get("/api/notifications/", {"status": "invalid"}).status_code, 400)

    def test_admin_list_paginates_without_loading_every_notification(self):
        self.queue()
        for sequence in range(25):
            event = OrderEvent.objects.create(order=self.order, status="pending", actor=self.customer)
            enqueue_order_notification(event)
        first = self.client.get("/api/notifications/")
        second = self.client.get("/api/notifications/", {"page": 2})
        self.assertEqual(first.data["count"], 26)
        self.assertEqual(len(first.data["results"]), 25)
        self.assertEqual(len(second.data["results"]), 1)
        self.assertIsNotNone(first.data["next"])
        self.assertIsNone(second.data["next"])

    def test_command_once_processes_mocked_transport(self):
        notification = self.queue()
        output = StringIO()
        with patch("delivery.notifications.bot_request", return_value={"message_id": 1}):
            call_command("process_notifications", "--once", stdout=output)
        notification.refresh_from_db()
        self.assertEqual(notification.status, "sent")
        self.assertIn("1", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("process_notifications", "--once", "--batch-size", "0")

    def test_interrupted_http_response_becomes_retryable_network_error(self):
        with patch("delivery.telegram.urlopen", side_effect=IncompleteRead(b"partial")):
            with self.assertRaises(URLError):
                bot_request("sendMessage", {})

    def test_transport_extracts_retry_after_without_exposing_token_url(self):
        body = BytesIO(json.dumps({"ok": False, "error_code": 429, "parameters": {"retry_after": 75}}).encode())
        response_error = HTTPError("https://api.telegram.org/botsecret-token/sendMessage", 429, "Limited", {}, body)
        with patch("delivery.telegram.urlopen", side_effect=response_error):
            with self.assertRaises(TelegramAPIError) as caught:
                bot_request("sendMessage", {})
        self.assertEqual(caught.exception.code, 429)
        self.assertEqual(caught.exception.retry_after, 75)
        self.assertNotIn("secret-token", str(caught.exception))
