from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.wsgi import get_wsgi_application
from waitress import serve

from delivery.preview import PreviewApplication


class Command(BaseCommand):
    help = "React build va API’ni faqat localhost’da HTTPS tunnel uchun ishga tushiradi."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=8765)

    def handle(self, *args, **options):
        if settings.DEBUG or settings.ENABLE_DEMO_AUTH or settings.SETTINGS_MODULE != "config.telegram_preview":
            raise CommandError("Bu buyruq faqat xavfsiz config.telegram_preview rejimida ishlaydi.")
        if not 1024 <= options["port"] <= 65535:
            raise CommandError("Port 1024–65535 oralig‘ida bo‘lsin.")
        application = PreviewApplication(get_wsgi_application(), settings.BASE_DIR.parent / "frontend/dist")
        self.stdout.write(self.style.SUCCESS(f"Telegram WebApp server: 127.0.0.1:{options['port']}"))
        serve(application, host="127.0.0.1", port=options["port"], threads=4, trusted_proxy="127.0.0.1", trusted_proxy_headers={"x-forwarded-proto"}, clear_untrusted_proxy_headers=True, expose_tracebacks=False, ident="Tezkor")
