from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from delivery.telegram import bot_request


class Command(BaseCommand):
    help = "Telegram webhook va Mini App menyusini sozlaydi; polling boshlamaydi."

    def add_arguments(self, parser):
        parser.add_argument("--replace-existing", action="store_true")

    def handle(self, *args, **options):
        origin = settings.WEBAPP_URL.rstrip("/")
        parsed = urlsplit(origin)
        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        if not settings.BOT_TOKEN or not secret or not getattr(settings, "TELEGRAM_WEBHOOK_ENABLED", False):
            raise CommandError("Webhook rejimi va maxfiy kalit sozlanishi kerak.")
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path:
            raise CommandError("Webhook uchun HTTPS origin kerak.")
        endpoint = origin + "/api/telegram/webhook/"
        try:
            info = bot_request("getWebhookInfo", {})
            if info.get("url") and info["url"] != endpoint and not options["replace_existing"]:
                raise CommandError("Boshqa webhook mavjud. Almashtirish uchun --replace-existing kerak.")
            bot_request("setWebhook", {"url": endpoint, "secret_token": secret, "max_connections": 2,
                                      "allowed_updates": ["message"], "drop_pending_updates": False})
            bot_request("setChatMenuButton", {"menu_button": {"type": "web_app", "text": "Buyurtma berish", "web_app": {"url": origin}}})
        except CommandError:
            raise
        except Exception:
            raise CommandError("Telegram webhook sozlanmadi. Tarmoq va bot tokenini tekshiring.") from None
        self.stdout.write("Telegram webhook va menyu sozlandi.")
