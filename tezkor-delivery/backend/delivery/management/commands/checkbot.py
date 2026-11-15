from urllib.error import URLError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from delivery.telegram import TelegramAPIError, bot_request


class Command(BaseCommand):
    help = "Bot tokenini Telegram orqali tekshiradi, tokenning o‘zini chiqarmaydi."

    def handle(self, *args, **options):
        if not settings.BOT_TOKEN:
            raise CommandError("BOT_TOKEN ni backend/.env faylida belgilang.")
        try:
            bot = bot_request("getMe", {})
        except TelegramAPIError as error:
            if error.code in {401, 404}:
                raise CommandError("Telegram tokenni qabul qilmadi. BotFather tokenini tekshiring.") from None
            raise CommandError(f"Telegram API HTTP {error.code} xatosini qaytardi.") from None
        except (URLError, TimeoutError, OSError):
            raise CommandError("Telegram tarmog‘iga ulanib bo‘lmadi. Internet va tarmoq ruxsatlarini tekshiring.") from None
        except (RuntimeError, ValueError, KeyError):
            raise CommandError("Telegram javobini tekshirib bo‘lmadi.") from None
        self.stdout.write(self.style.SUCCESS(f"Token tasdiqlandi: @{bot['username']} (ID: {bot['id']})"))
        if not settings.WEBAPP_URL:
            self.stdout.write("WEBAPP_URL hali belgilanmagan. Mini App uchun HTTPS manzil kerak.")
        if not settings.TELEGRAM_ADMIN_IDS:
            self.stdout.write("TELEGRAM_ADMIN_IDS hali belgilanmagan. Admin uchun shaxsiy Telegram ID kerak.")
