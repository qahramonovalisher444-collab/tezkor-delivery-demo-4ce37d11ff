from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


@override_settings(BOT_TOKEN="test-token-only", WEBAPP_URL="https://example.test")
class BotStartupTests(SimpleTestCase):
    def test_existing_webhook_is_not_deleted_implicitly(self):
        with patch("delivery.management.commands.runbot.bot_request", return_value={"url": "https://existing.test/webhook"}) as sender:
            with self.assertRaises(CommandError):
                call_command("runbot", stdout=StringIO())
        self.assertEqual([call.args[0] for call in sender.call_args_list], ["getWebhookInfo"])

    def test_configure_only_sets_menu_without_polling_or_messages(self):
        with patch("delivery.management.commands.runbot.bot_request", side_effect=[{"url": "https://existing.test/webhook"}, True]) as sender:
            call_command("runbot", "--configure-only", stdout=StringIO())
        self.assertEqual([call.args[0] for call in sender.call_args_list], ["getWebhookInfo", "setChatMenuButton"])

    def test_explicit_webhook_replacement_preserves_pending_updates(self):
        with patch("delivery.management.commands.runbot.bot_request", side_effect=[{"url": "https://existing.test/webhook"}, True, True, KeyboardInterrupt()]) as sender:
            call_command("runbot", "--replace-webhook", stdout=StringIO())
        self.assertEqual(sender.call_args_list[1].args, ("deleteWebhook", {"drop_pending_updates": False}))
        self.assertNotIn("sendMessage", [call.args[0] for call in sender.call_args_list])

    def test_ready_marker_is_written_after_menu_configuration(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "bot.ready"
            with patch("delivery.management.commands.runbot.bot_request", side_effect=[{}, True]):
                call_command("runbot", "--configure-only", "--ready-file", str(marker), stdout=StringIO())
            self.assertEqual(marker.read_text(), "https://example.test")

    def test_webhook_refusal_does_not_write_ready_marker(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "bot.ready"
            with patch("delivery.management.commands.runbot.bot_request", return_value={"url": "https://existing.test/webhook"}):
                with self.assertRaises(CommandError):
                    call_command("runbot", "--ready-file", str(marker), stdout=StringIO())
            self.assertFalse(marker.exists())

    def test_menu_failure_does_not_write_ready_marker(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "bot.ready"
            with patch("delivery.management.commands.runbot.bot_request", side_effect=[{}, RuntimeError("transport unavailable")]):
                with self.assertRaises(CommandError):
                    call_command("runbot", "--ready-file", str(marker), stdout=StringIO())
            self.assertFalse(marker.exists())
