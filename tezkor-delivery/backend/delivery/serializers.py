import hashlib
import json
import re
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .exceptions import OrderRequestConflict
from .models import Category, Order, OrderEvent, OrderItem, Product, User
from .notifications import enqueue_order_notification
from .permissions import can_manage_user


def validate_phone_number(value):
    normalized = re.sub(r"[\s()\-]", "", value)
    if not re.fullmatch(r"\+998\d{9}", normalized):
        raise serializers.ValidationError("Telefon +998XXXXXXXXX formatida bo‘lsin.")
    return normalized


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "username", "role", "phone", "is_active", "telegram_id"]

    def get_role(self, user):
        return "admin" if user.is_delivery_admin else user.role

    def get_name(self, user):
        return user.get_full_name() or user.username


class UserManagementSerializer(UserSerializer):
    active_deliveries = serializers.IntegerField(read_only=True, default=0)
    can_manage = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["active_deliveries", "can_manage"]

    def get_can_manage(self, user):
        return can_manage_user(self.context["request"].user, user)


class ProfileSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["first_name", "last_name", "default_address"]
        read_only_fields = ["id", "username", "role", "is_active", "telegram_id"]

    def validate_phone(self, value):
        return validate_phone_number(value) if value else ""

    def validate_default_address(self, value):
        if value and len(value) < 5:
            raise serializers.ValidationError("Manzil kamida 5 belgidan iborat bo‘lsin.")
        return value

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if validated_data:
            instance.save(update_fields=list(validated_data))
        return instance


class OrderContactSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        fields = ["id", "name", "phone"]


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, default=0)
    icon = serializers.ChoiceField(choices=["burger", "pizza", "drink", "salad", "snack", "utensils"], required=False)
    position = serializers.IntegerField(min_value=0, max_value=10000, required=False)

    class Meta:
        model = Category
        fields = ["id", "name", "icon", "position", "product_count"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "category", "category_name", "name", "description", "price", "image_url", "badge", "weight", "is_available"]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "unit_price", "quantity"]


class OrderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderEvent
        fields = ["id", "status", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    events = OrderEventSerializer(many=True, read_only=True)
    customer = OrderContactSerializer(read_only=True)
    courier = OrderContactSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "customer", "courier", "status", "status_label", "address", "delivery_latitude", "delivery_longitude", "phone", "note", "items", "events", "subtotal", "delivery_fee", "total", "payment_method", "created_at", "updated_at"]


class CartItemSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=30)


class CreateOrderSerializer(serializers.Serializer):
    request_id = serializers.UUIDField(required=False)
    items = CartItemSerializer(many=True, allow_empty=False, max_length=50)
    address = serializers.CharField(min_length=5, max_length=400)
    delivery_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=Decimal("-90"), max_value=Decimal("90"), required=False, allow_null=True, default=None)
    delivery_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=Decimal("-180"), max_value=Decimal("180"), required=False, allow_null=True, default=None)
    phone = serializers.CharField(max_length=24)
    note = serializers.CharField(max_length=600, required=False, allow_blank=True, default="")
    save_details = serializers.BooleanField(required=False, default=False)

    def validate_phone(self, value):
        return validate_phone_number(value)

    def validate_items(self, items):
        product_ids = [item["product"] for item in items]
        if len(set(product_ids)) != len(product_ids):
            raise serializers.ValidationError("Mahsulot takrorlangan.")
        return items

    def validate(self, values):
        if (values.get("delivery_latitude") is None) != (values.get("delivery_longitude") is None):
            raise serializers.ValidationError({"delivery_latitude": "Xarita uchun ikkala koordinata birga yuborilishi kerak."})
        return values

    @transaction.atomic
    def create(self, validated_data):
        customer = User.objects.select_for_update().get(pk=self.context["request"].user.pk)
        if not customer.is_active or customer.role != User.Role.CUSTOMER or customer.is_delivery_admin:
            raise PermissionDenied("Bu hisob orqali buyurtma yaratib bo‘lmaydi.")
        request_id = validated_data.pop("request_id", None)
        fingerprint_data = {**validated_data, "items": sorted(validated_data["items"], key=lambda item: item["product"])}
        for field in ["delivery_latitude", "delivery_longitude"]:
            if fingerprint_data.get(field) is None:
                fingerprint_data.pop(field, None)
            else:
                fingerprint_data[field] = str(fingerprint_data[field])
        fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.was_replayed = False
        if request_id:
            existing = Order.objects.filter(customer=customer, request_id=request_id).first()
            if existing:
                if existing.request_fingerprint != fingerprint:
                    raise OrderRequestConflict()
                self.was_replayed = True
                return existing
        save_details = validated_data.pop("save_details")
        items = validated_data.pop("items")
        products = {product.id: product for product in Product.objects.select_for_update().filter(id__in=[item["product"] for item in items])}
        if len(products) != len(items) or any(not product.is_available for product in products.values()):
            raise serializers.ValidationError({"items": "Ayrim mahsulotlar hozir mavjud emas. Savatni yangilang."})
        subtotal = sum((products[item["product"]].price * item["quantity"] for item in items), Decimal(0))
        delivery_fee = Decimal(settings.DELIVERY_FEE)
        order = Order.objects.create(customer=customer, subtotal=subtotal, delivery_fee=delivery_fee, total=subtotal + delivery_fee, request_id=request_id, request_fingerprint=fingerprint if request_id else "", **validated_data)
        OrderItem.objects.bulk_create([
            OrderItem(order=order, product=products[item["product"]], product_name=products[item["product"]].name, unit_price=products[item["product"]].price, quantity=item["quantity"])
            for item in items
        ])
        event = OrderEvent.objects.create(order=order, status=order.status, actor=order.customer)
        enqueue_order_notification(event)
        if save_details:
            customer.phone = order.phone
            customer.default_address = order.address
            customer.save(update_fields=["phone", "default_address"])
        return order


class ChangeStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)


class AssignCourierSerializer(serializers.Serializer):
    courier = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.COURIER, is_active=True))


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class ChangeActivitySerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class OrderFilterSerializer(serializers.Serializer):
    search = serializers.CharField(max_length=120, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=[*Order.Status.values, "active"], required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, values):
        if values.get("date_from") and values.get("date_to") and values["date_from"] > values["date_to"]:
            raise serializers.ValidationError("Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.")
        return values


class UserFilterSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)
    search = serializers.CharField(max_length=120, required=False, allow_blank=True)
