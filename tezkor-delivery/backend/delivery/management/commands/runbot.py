import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from delivery.telegram import bot_request


class Command(BaseCommand):
    help = "Telegram botni long polling orqali ishga tushiradi."

    def add_arguments(self, parser):
        parser.add_argument("--configure-only", action="store_true")
        parser.add_argument("--replace-webhook", action="store_true")
        parser.add_argument("--ready-file", help="Menyu sozlangandan keyin tayyorlik faylini yozadi")

    def handle(self, *args, **options):
        if not settings.BOT_TOKEN:
            raise CommandError("BOT_TOKEN ni .env faylida belgilang.")
        webapp_url = urlparse(settings.WEBAPP_URL)
        if webapp_url.scheme != "https" or not webapp_url.netloc:
            raise CommandError("WEBAPP_URL haqiqiy HTTPS manzil bo‘lishi kerak.")
        try:
            webhook = bot_request("getWebhookInfo", {})
            if webhook.get("url") and not options["configure_only"]:
                if not options["replace_webhook"]:
                    raise CommandError("Botda webhook bor. Uni almashtirish kerak bo‘lsa runbot --replace-webhook ni aniq tanlang.")
                bot_request("deleteWebhook", {"drop_pending_updates": False})
            bot_request("setChatMenuButton", {"menu_button": {"type": "web_app", "text": "Buyurtma berish", "web_app": {"url": settings.WEBAPP_URL}}})
        except CommandError:
            raise
        except Exception:
            raise CommandError("Telegram bilan ulanish amalga oshmadi. Token va internetni tekshiring.") from None
        if options["ready_file"]:
            try:
                Path(options["ready_file"]).write_text(settings.WEBAPP_URL, encoding="utf-8")
            except OSError:
                raise CommandError("Bot tayyorlik fayli yozilmadi.") from None
        if options["configure_only"]:
            self.stdout.write(self.style.SUCCESS("Bot menyusi sozlandi. Polling va xabar yuborish boshlanmadi."))
            return
        self.stdout.write(self.style.SUCCESS("Tezkor bot ishga tushdi. To‘xtatish: Ctrl+C"))
        offset = 0
        try:
            while True:
                try:
                    updates = bot_request("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message"]}, timeout=35)
                    for update in updates:
                        message = update.get("message", {})
                        if message.get("chat", {}).get("type") == "private" and message.get("text", "").split(" ")[0] in {"/start", "/menu"}:
                            bot_request("sendMessage", {
                                "chat_id": message["chat"]["id"],
                                "text": "Tezkor’ga xush kelibsiz! 🍔\nSevimli taomingizni tanlang — biz yetkazamiz.",
                                "reply_markup": {"inline_keyboard": [[{"text": "🍽 Menyuni ochish", "web_app": {"url": settings.WEBAPP_URL}}]]},
                            })
                        offset = update["update_id"] + 1
                except (URLError, TimeoutError, RuntimeError, OSError):
                    self.stderr.write("Telegram ulanishida xatolik. 5 soniyadan so‘ng qayta uriniladi.")
                    time.sleep(5)
        except KeyboardInterrupt:
            self.stdout.write("Bot to‘xtatildi.")
