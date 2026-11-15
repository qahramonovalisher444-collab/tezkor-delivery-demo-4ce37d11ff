import time

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections

from delivery.notifications import process_due_notifications


class Command(BaseCommand):
    help = "Bazadagi Telegram xabarnomalarini yuboradi va vaqtinchalik xatolarda qayta urinadi."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--batch-size", type=int, default=20)
        parser.add_argument("--poll-interval", type=int, default=2)

    def handle(self, *args, **options):
        if not 1 <= options["batch_size"] <= 100 or not 1 <= options["poll_interval"] <= 60:
            raise CommandError("batch-size 1–100, poll-interval 1–60 oralig‘ida bo‘lsin.")
        try:
            while True:
                close_old_connections()
                try:
                    processed = process_due_notifications(options["batch_size"])
                except DatabaseError:
                    if options["once"]:
                        raise CommandError("Xabarnoma bazasiga ulanib bo‘lmadi. Migratsiya va bazani tekshiring.") from None
                    self.stderr.write("Xabarnoma bazasi tayyor emas. Migratsiya va bazani tekshiring.")
                    time.sleep(5)
                    continue
                if processed or options["once"]:
                    self.stdout.write(f"Qayta ishlangan xabarnomalar: {processed}")
                if options["once"]:
                    break
                time.sleep(options["poll_interval"])
        except KeyboardInterrupt:
            self.stdout.write("Xabarnoma xizmati to‘xtatildi.")
