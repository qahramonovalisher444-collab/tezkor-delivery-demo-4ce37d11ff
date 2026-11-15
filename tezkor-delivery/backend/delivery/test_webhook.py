import base64
from io import StringIO
import json
import os
from unittest.mock import patch
import zlib

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings

from .models import Category, DataImportReceipt, Product, TelegramWebhookUpdate, User


@override_settings(TELEGRAM_WEBHOOK_ENABLED=True, TELEGRAM_WEBHOOK_SECRET="test-secret-" + "x" * 36,
                   BOT_TOKEN="test-only", WEBAPP_URL="https://example.test")
class WebhookTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.update = {"update_id": 101, "message": {"chat": {"id": 123, "type": "private"}, "text": "/start"}}

    def send(self, data=None, secret="test-secret-" + "x" * 36):
        return self.client.post("/api/telegram/webhook/", json.dumps(data if data is not None else self.update),
                                content_type="application/json", secure=True,
                                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret)

    def test_signed_webhook_replies_with_mini_app_without_csrf_cookie(self):
        with patch("delivery.webhook.bot_request", return_value={"message_id": 12}) as sender:
            self.assertEqual(self.send().status_code, 200)
        self.assertEqual(sender.call_args.args[0], "sendMessage")
        self.assertEqual(sender.call_args.args[1]["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"], "https://example.test")
        self.assertTrue(TelegramWebhookUpdate.objects.filter(pk=101).exists())

    def test_wrong_or_missing_secret_does_not_send_or_write(self):
        with patch("delivery.webhook.bot_request") as sender:
            for secret in ["", "wrong", "noto‘g‘ri"]:
                self.assertEqual(self.send(secret=secret).status_code, 403)
        sender.assert_not_called()
        self.assertFalse(TelegramWebhookUpdate.objects.exists())

    def test_retried_update_does_not_send_a_second_message(self):
        with patch("delivery.webhook.bot_request", return_value={"message_id": 12}) as sender:
            self.assertEqual(self.send().status_code, 200)
            self.assertEqual(self.send().status_code, 200)
        self.assertEqual(sender.call_count, 1)

    def test_failed_send_is_retryable_and_receipt_is_rolled_back(self):
        with patch("delivery.webhook.bot_request", side_effect=OSError("private transport details")):
            response = self.send()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"private transport", response.content)
        self.assertFalse(TelegramWebhookUpdate.objects.exists())
        with patch("delivery.webhook.bot_request", return_value={"message_id": 13}):
            self.assertEqual(self.send().status_code, 200)

    def test_unsupported_and_group_updates_do_not_send(self):
        with patch("delivery.webhook.bot_request") as sender:
            self.assertEqual(self.send({"update_id": 102}).status_code, 200)
            self.update["message"]["chat"]["type"] = "group"
            self.assertEqual(self.send().status_code, 200)
        sender.assert_not_called()

    def test_invalid_update_ids_are_rejected(self):
        for value in [None, True, -1, 2**63, "101"]:
            self.assertEqual(self.send({"update_id": value}).status_code, 400)
        self.assertFalse(TelegramWebhookUpdate.objects.exists())

    @override_settings(TELEGRAM_WEBHOOK_ENABLED=False)
    def test_local_polling_mode_does_not_expose_webhook(self):
        with patch("delivery.webhook.bot_request") as sender:
            self.assertEqual(self.send().status_code, 404)
        sender.assert_not_called()

    def test_method_content_type_and_size_limits(self):
        self.assertEqual(self.client.get("/api/telegram/webhook/", secure=True).status_code, 405)
        self.assertEqual(self.client.post("/api/telegram/webhook/", "{}", content_type="text/plain", secure=True,
                                         HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="test-secret-" + "x" * 36).status_code, 415)
        self.assertEqual(self.send({"update_id": 101, "padding": "x" * 131072}).status_code, 400)


@override_settings(TELEGRAM_WEBHOOK_ENABLED=True, TELEGRAM_WEBHOOK_SECRET="test-secret-" + "x" * 36,
                   BOT_TOKEN="test-only", WEBAPP_URL="https://example.test")
class ConfigureWebhookTests(SimpleTestCase):
    def test_configures_webhook_and_menu_without_dropping_updates(self):
        with patch("delivery.management.commands.configure_webhook.bot_request", side_effect=[{}, True, True]) as sender:
            call_command("configure_webhook", stdout=StringIO())
        self.assertEqual([call.args[0] for call in sender.call_args_list], ["getWebhookInfo", "setWebhook", "setChatMenuButton"])
        self.assertFalse(sender.call_args_list[1].args[1]["drop_pending_updates"])
        self.assertEqual(sender.call_args_list[1].args[1]["url"], "https://example.test/api/telegram/webhook/")

    def test_existing_other_webhook_is_preserved(self):
        with patch("delivery.management.commands.configure_webhook.bot_request", return_value={"url": "https://other.test/endpoint"}) as sender:
            with self.assertRaises(CommandError):
                call_command("configure_webhook", stdout=StringIO())
        self.assertEqual(sender.call_count, 1)

    @override_settings(TELEGRAM_WEBHOOK_ENABLED=False)
    def test_disabled_configuration_does_not_call_telegram(self):
        with patch("delivery.management.commands.configure_webhook.bot_request") as sender:
            with self.assertRaises(CommandError):
                call_command("configure_webhook", stdout=StringIO())
        sender.assert_not_called()


class InitialDataTests(TestCase):
    def fixture(self, records):
        return base64.b64encode(zlib.compress(json.dumps(records).encode())).decode()

    def run_import(self, records):
        with patch.dict(os.environ, {"INITIAL_IMPORT_B64": self.fixture(records)}):
            call_command("import_initial_data", stdout=StringIO())

    def test_import_once_does_not_overwrite_later_changes(self):
        data = [{"model": "delivery.category", "pk": 4, "fields": {"name": "Burger", "icon": "burger", "position": 0}}]
        self.run_import(data)
        Category.objects.filter(pk=4).update(name="Yangilangan")
        self.run_import(data)
        self.assertEqual(Category.objects.get(pk=4).name, "Yangilangan")
        self.assertEqual(DataImportReceipt.objects.count(), 1)

    def test_new_snapshot_cannot_replace_live_users(self):
        User.objects.create_user(username="real-user", telegram_id=12345)
        with self.assertRaises(CommandError):
            self.run_import([{"model": "delivery.category", "pk": 4, "fields": {"name": "Burger"}}])
        self.assertTrue(User.objects.filter(username="real-user").exists())

    def test_partial_import_failure_rolls_back_unused_menu_and_receipt(self):
        original = Category.objects.create(name="Existing menu")
        with self.assertRaises(CommandError):
            self.run_import([{"model": "delivery.category", "pk": 4, "fields": {"name": "Burger"}},
                             {"model": "delivery.product", "pk": 5, "fields": {"category": 999, "name": "Invalid", "price": None}}])
        self.assertTrue(Category.objects.filter(pk=original.pk, name="Existing menu").exists())
        self.assertFalse(Product.objects.exists())
        self.assertFalse(DataImportReceipt.objects.exists())

    def test_auth_tokens_and_non_delivery_models_are_rejected(self):
        with self.assertRaises(CommandError):
            self.run_import([{"model": "authtoken.token", "pk": "not-a-token", "fields": {}}])

    def test_invalid_encoded_data_is_rejected_without_echoing_it(self):
        with patch.dict(os.environ, {"INITIAL_IMPORT_B64": "private-not-base64"}):
            with self.assertRaises(CommandError) as caught:
                call_command("import_initial_data", stdout=StringIO())
        self.assertNotIn("private-not-base64", str(caught.exception))
