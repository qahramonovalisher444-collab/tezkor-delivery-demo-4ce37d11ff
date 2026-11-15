from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .validators import validate_image_url


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        COURIER = "courier", "Kuryer"
        CUSTOMER = "customer", "Foydalanuvchi"

    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=24, blank=True)
    default_address = models.CharField(max_length=400, blank=True)

    @property
    def is_delivery_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    icon = models.CharField(max_length=20, default="utensils")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=1000)
    price = models.DecimalField(max_digits=12, decimal_places=0, validators=[MinValueValidator(1)])
    image_url = models.CharField(blank=True, max_length=600, validators=[validate_image_url])
    badge = models.CharField(max_length=30, blank=True)
    weight = models.CharField(max_length=40, blank=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=models.Q(price__gt=0), name="product_price_positive")]

    def __str__(self):
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Yangi"
        CONFIRMED = "confirmed", "Tasdiqlangan"
        PREPARING = "preparing", "Tayyorlanmoqda"
        READY = "ready", "Tayyor"
        DELIVERING = "delivering", "Yo‘lda"
        DELIVERED = "delivered", "Yetkazildi"
        CANCELLED = "cancelled", "Bekor qilingan"

    customer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders")
    courier = models.ForeignKey(User, on_delete=models.PROTECT, related_name="deliveries", null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    address = models.CharField(max_length=400)
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=24)
    note = models.CharField(max_length=600, blank=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=0)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=0)
    total = models.DecimalField(max_digits=18, decimal_places=0)
    payment_method = models.CharField(max_length=12, default="cash", editable=False)
    request_id = models.UUIDField(null=True, blank=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["customer", "request_id"], name="unique_order_request_per_customer"),
            models.CheckConstraint(
                condition=(models.Q(delivery_latitude__isnull=True, delivery_longitude__isnull=True) | models.Q(delivery_latitude__isnull=False, delivery_longitude__isnull=False, delivery_latitude__gte=-90, delivery_latitude__lte=90, delivery_longitude__gte=-180, delivery_longitude__lte=180)),
                name="order_delivery_coordinates_valid",
            ),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=12, decimal_places=0)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=16, choices=Order.Status.choices)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class OrderNotification(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        PROCESSING = "processing", "Yuborilmoqda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xato"

    event = models.OneToOneField(OrderEvent, on_delete=models.CASCADE, related_name="notification")
    chat_id = models.BigIntegerField()
    text = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    retry_after_until = models.DateTimeField(null=True, blank=True, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    lock_token = models.UUIDField(null=True, blank=True)
    last_error = models.CharField(max_length=240, blank=True)
    message_id = models.BigIntegerField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]


class TelegramWebhookUpdate(models.Model):
    update_id = models.PositiveBigIntegerField(primary_key=True)
    processed_at = models.DateTimeField(default=timezone.now)


class DataImportReceipt(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    applied_at = models.DateTimeField(default=timezone.now)
