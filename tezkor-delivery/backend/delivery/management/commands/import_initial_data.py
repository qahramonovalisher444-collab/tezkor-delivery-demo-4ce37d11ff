import base64
import hashlib
import json
import os
import zlib

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from delivery.models import Category, DataImportReceipt, Order, OrderEvent, OrderItem, OrderNotification, Product, User


ALLOWED_MODELS = [Category, User, Product, Order, OrderItem, OrderEvent, OrderNotification]


class Command(BaseCommand):
    help = "Maxfiy environment snapshotini faqat bo‘sh biznes bazasiga bir marta ko‘chiradi."

    def handle(self, *args, **options):
        encoded = os.getenv("INITIAL_IMPORT_B64", "")
        if not encoded:
            return
        try:
            if len(encoded) > 200000:
                raise ValueError
            compressed = base64.b64decode(encoded, validate=True)
            decoder = zlib.decompressobj()
            raw = decoder.decompress(compressed, 2_000_000)
            if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
                raise ValueError
            records = json.loads(raw)
            allowed = {model._meta.label_lower for model in ALLOWED_MODELS}
            if not isinstance(records, list) or not records or any(not isinstance(row, dict) or row.get("model") not in allowed for row in records):
                raise ValueError
        except (ValueError, TypeError, zlib.error, UnicodeError):
            raise CommandError("Boshlang‘ich ma’lumot snapshoti yaroqsiz.") from None
        digest = hashlib.sha256(raw).hexdigest()
        try:
            with transaction.atomic():
                if DataImportReceipt.objects.filter(pk=digest).exists():
                    self.stdout.write("Boshlang‘ich ma’lumot avval ko‘chirilgan; qayta yozilmadi.")
                    return
                if DataImportReceipt.objects.exists() or Order.objects.exists() or User.objects.exists():
                    raise CommandError("Bazada foydalanuvchi/buyurtmalar bor; avtomatik almashtirish rad etildi.")
                # The initial cloud health check may already have seeded an unused menu.
                Product.objects.all().delete()
                Category.objects.all().delete()
                for record in serializers.deserialize("json", json.dumps(records)):
                    record.save()
                with connection.cursor() as cursor:
                    for statement in connection.ops.sequence_reset_sql(no_style(), ALLOWED_MODELS):
                        cursor.execute(statement)
                DataImportReceipt.objects.create(digest=digest)
        except CommandError:
            raise
        except Exception:
            raise CommandError("Ma’lumot ko‘chirilmadi; o‘zgarishlar bekor qilindi.") from None
        self.stdout.write(f"Boshlang‘ich ma’lumot ko‘chirildi: {len(records)} yozuv.")
