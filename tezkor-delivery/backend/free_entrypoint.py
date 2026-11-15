import os
from pathlib import Path
import signal
import sys
import threading

from cloud_worker import supervise


BACKEND = Path(__file__).resolve().parent


def prepare_database():
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", interactive=False, verbosity=1)
    call_command("import_initial_data")
    call_command("seed_menu")
    from django.conf import settings
    if settings.TELEGRAM_WEBHOOK_ENABLED:
        call_command("configure_webhook")


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.free")
    stopping = threading.Event()
    for stop_signal in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(stop_signal, lambda *_: stopping.set())
    prepare_database()
    if stopping.is_set():
        return
    print("Bepul Render: web server va xabarnoma xizmati boshlanmoqda.", flush=True)
    supervise([
        [sys.executable, "-m", "gunicorn", "config.production_wsgi:application", "--config", "gunicorn.conf.py"],
        [sys.executable, str(BACKEND / "manage.py"), "process_notifications", "--poll-interval", "5"],
    ], stopping)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Bepul hostingni ishga tushirish bajarilmadi. Sozlamalar, baza va Telegram ulanishini tekshiring.", file=sys.stderr, flush=True)
        raise SystemExit(1) from None
