from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from delivery.models import Category, Product


class Command(BaseCommand):
    help = "Faqat bo‘sh bazaga restoran menyusini yaratadi; demo hisob yoki buyurtma qo‘shmaydi."

    @transaction.atomic
    def handle(self, *args, **options):
        if Category.objects.exists() or Product.objects.exists():
            self.stdout.write("Menyu allaqachon mavjud; o‘zgartirilmadi.")
            return
        call_command("seed_demo", menu_only=True, stdout=self.stdout, stderr=self.stderr)
