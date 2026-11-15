import re

from django.conf import settings
from django.db import DatabaseError, connection, transaction
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Concat
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import Category, Order, OrderEvent, Product, User
from .permissions import AdminOrReadOnly, IsDeliveryAdmin, can_manage_user
from .serializers import AssignCourierSerializer, CategorySerializer, ChangeActivitySerializer, ChangeRoleSerializer, ChangeStatusSerializer, CreateOrderSerializer, OrderFilterSerializer, OrderSerializer, ProductSerializer, ProfileSerializer, UserFilterSerializer, UserManagementSerializer
from .notifications import enqueue_order_notification
from .telegram import validate_init_data


class LoginThrottle(ScopedRateThrottle):
    def get_rate(self):
        return self.THROTTLE_RATES["login"]

    def allow_request(self, request, view):
        view.throttle_scope = "login"
        return super().allow_request(request, view)


def login_response(user):
    if not user.is_active:
        raise PermissionDenied("Hisob bloklangan.")
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": ProfileSerializer(user).data})


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET", "HEAD"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return Response({"status": "unavailable"}, status=503)
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
def app_config(request):
    return Response({"demo_auth": settings.ENABLE_DEMO_AUTH, "delivery_fee": settings.DELIVERY_FEE, "currency": "UZS", "restaurant": "Tezkor"})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def telegram_login(request):
    init_data = request.data.get("init_data", "")
    if not isinstance(init_data, str) or len(init_data) > 16384:
        raise ValidationError("Noto‘g‘ri kirish ma’lumotlari.")
    telegram_user = validate_init_data(init_data)
    user, created = User.objects.get_or_create(telegram_id=telegram_user["id"], defaults={"username": f"tg_{telegram_user['id']}"})
    updated_fields = []
    if created:
        user.set_unusable_password()
        user.first_name = str(telegram_user.get("first_name", ""))[:150]
        user.last_name = str(telegram_user.get("last_name", ""))[:150]
        updated_fields.extend(["password", "first_name", "last_name"])
    if user.telegram_id in settings.TELEGRAM_ADMIN_IDS:
        user.role = User.Role.ADMIN
        updated_fields.append("role")
    if updated_fields:
        user.save(update_fields=updated_fields)
    return login_response(user)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def demo_login(request):
    if not settings.ENABLE_DEMO_AUTH:
        raise PermissionDenied("Demo kirish o‘chirilgan.")
    role = request.data.get("role", "customer")
    if role not in User.Role.values:
        raise ValidationError("Noto‘g‘ri rol.")
    user = get_object_or_404(User, username=f"demo_{role}", role=role)
    return login_response(user)


@api_view(["GET", "PATCH"])
def me(request):
    if request.method == "PATCH":
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    return Response(ProfileSerializer(request.user).data)


@api_view(["POST"])
def logout(request):
    request.auth.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.annotate(product_count=Count("products")).order_by("position", "id")
    serializer_class = CategorySerializer
    permission_classes = [AdminOrReadOnly]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        try:
            category.delete()
        except ProtectedError:
            raise ValidationError("Bu kategoriyada mahsulotlar bor. Avval ularni boshqa kategoriyaga o‘tkazing.") from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [AdminOrReadOnly]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        products = Product.objects.select_related("category").all()
        if not self.request.user.is_authenticated or not self.request.user.is_delivery_admin:
            products = products.filter(is_available=True)
        category = self.request.query_params.get("category")
        if category:
            if not category.isdigit():
                raise ValidationError({"category": "Son kiriting."})
            products = products.filter(category_id=int(category))
        search = self.request.query_params.get("search", "").strip()
        return products.filter(name__icontains=search) if search else products


class OrderViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderSerializer

    def get_queryset(self):
        orders = Order.objects.select_related("customer", "courier").prefetch_related("items", "events")
        user = self.request.user
        if not user.is_delivery_admin:
            orders = orders.filter(courier=user) if user.role == User.Role.COURIER else orders.filter(customer=user)
        if self.action != "list":
            return orders
        serializer = OrderFilterSerializer(data=self.request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data
        requested_status = filters.get("status")
        if requested_status == "active":
            orders = orders.exclude(status__in=["delivered", "cancelled"])
        elif requested_status:
            orders = orders.filter(status=requested_status)
        if filters.get("date_from"):
            orders = orders.filter(created_at__date__gte=filters["date_from"])
        if filters.get("date_to"):
            orders = orders.filter(created_at__date__lte=filters["date_to"])
        search = filters.get("search", "").strip()
        if search:
            orders = orders.annotate(customer_full_name=Concat("customer__first_name", Value(" "), "customer__last_name"))
            query = Q(address__icontains=search) | Q(phone__icontains=search) | Q(customer_full_name__icontains=search) | Q(items__product_name__icontains=search)
            order_number = search.removeprefix("#")
            if order_number.isascii() and order_number.isdigit() and len(order_number) <= 19 and int(order_number) < 2**63:
                query |= Q(pk=int(order_number))
            phone_search = re.sub(r"[\s()\-]", "", search)
            if len(phone_search) >= 3 and phone_search.removeprefix("+").isascii() and phone_search.removeprefix("+").isdigit():
                query |= Q(phone__icontains=phone_search)
            orders = orders.filter(query).distinct()
        return orders

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.CUSTOMER or request.user.is_delivery_admin:
            raise PermissionDenied("Buyurtmani foydalanuvchi yaratadi.")
        serializer = CreateOrderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK if serializer.was_replayed else status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="status")
    @transaction.atomic
    def change_status(self, request, pk=None):
        visible_order = self.get_object()
        order = Order.objects.select_for_update().get(pk=visible_order.pk)
        serializer = ChangeStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        next_status = serializer.validated_data["status"]
        transitions = {
            "pending": {"confirmed", "cancelled"}, "confirmed": {"preparing", "cancelled"},
            "preparing": {"ready", "cancelled"}, "ready": {"delivering", "cancelled"},
            "delivering": {"delivered"}, "delivered": set(), "cancelled": set(),
        }
        user = request.user
        if not user.is_delivery_admin:
            if user.role == User.Role.COURIER:
                if order.courier_id != user.id or (order.status, next_status) not in {("ready", "delivering"), ("delivering", "delivered")}:
                    raise PermissionDenied("Bu holatni o‘zgartira olmaysiz.")
            elif order.customer_id != user.id or (order.status, next_status) != ("pending", "cancelled"):
                raise PermissionDenied("Faqat yangi buyurtmani bekor qilish mumkin.")
        if next_status not in transitions[order.status]:
            raise ValidationError("Buyurtma holatlari ketma-ketligiga rioya qiling.")
        if next_status == Order.Status.DELIVERING and not order.courier_id:
            raise ValidationError("Avval kuryer tayinlang.")
        order.status = next_status
        order.save(update_fields=["status", "updated_at"])
        event = OrderEvent.objects.create(order=order, status=next_status, actor=user)
        enqueue_order_notification(event)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"], permission_classes=[IsDeliveryAdmin])
    @transaction.atomic
    def assign(self, request, pk=None):
        order = get_object_or_404(Order.objects.select_for_update(), pk=pk)
        if order.status in {"delivering", "delivered", "cancelled"}:
            raise ValidationError("Bu buyurtmaga kuryer tayinlab bo‘lmaydi.")
        serializer = AssignCourierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        courier = User.objects.select_for_update().get(pk=serializer.validated_data["courier"].pk)
        if not courier.is_active or courier.role != User.Role.COURIER or courier.is_delivery_admin:
            raise ValidationError("Faol kuryerni tanlang.")
        order.courier = courier
        order.save(update_fields=["courier", "updated_at"])
        return Response(OrderSerializer(order).data)


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = UserManagementSerializer
    permission_classes = [IsDeliveryAdmin]
    queryset = User.objects.order_by("-date_joined", "-id")

    def get_queryset(self):
        users = super().get_queryset().annotate(active_deliveries=Count("deliveries", filter=~Q(deliveries__status__in=["delivered", "cancelled"]), distinct=True))
        if self.action != "list":
            return users
        serializer = UserFilterSerializer(data=self.request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data
        if filters.get("role"):
            users = users.filter(Q(role=User.Role.ADMIN) | Q(is_superuser=True)) if filters["role"] == User.Role.ADMIN else users.filter(role=filters["role"], is_superuser=False)
        if "is_active" in filters:
            users = users.filter(is_active=filters["is_active"])
        search = filters.get("search", "").strip()
        if search:
            users = users.annotate(full_name=Concat("first_name", Value(" "), "last_name"))
            query = Q(full_name__icontains=search) | Q(username__icontains=search) | Q(phone__icontains=search)
            if search.isascii() and search.isdigit() and len(search) <= 16 and int(search) < 2**52:
                query |= Q(telegram_id=int(search))
            users = users.filter(query)
        return users

    @action(detail=True, methods=["post"], url_path="role")
    @transaction.atomic
    def change_role(self, request, pk=None):
        user = get_object_or_404(User.objects.select_for_update(), pk=pk)
        serializer = ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not can_manage_user(request.user, user):
            raise ValidationError("Bu hisobning rolini bu yerdan o‘zgartirib bo‘lmaydi.")
        next_role = serializer.validated_data["role"]
        if user.role == next_role:
            return Response(self.get_serializer(self.get_queryset().get(pk=user.pk)).data)
        if user.deliveries.exclude(status__in=["delivered", "cancelled"]).exists():
            raise ValidationError("Kuryerning faol buyurtmalari bor.")
        if user.orders.exclude(status__in=["delivered", "cancelled"]).exists():
            raise ValidationError("Foydalanuvchining faol buyurtmalari bor. Avval ularni yakunlang.")
        user.role = next_role
        user.save(update_fields=["role"])
        Token.objects.filter(user=user).delete()
        return Response(self.get_serializer(self.get_queryset().get(pk=user.pk)).data)

    @action(detail=True, methods=["post"], url_path="activity")
    @transaction.atomic
    def change_activity(self, request, pk=None):
        user = get_object_or_404(User.objects.select_for_update(), pk=pk)
        serializer = ChangeActivitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not can_manage_user(request.user, user):
            raise ValidationError("Bu hisobni bu yerdan bloklab yoki faollashtirib bo‘lmaydi.")
        is_active = serializer.validated_data["is_active"]
        if user.is_active == is_active:
            return Response(self.get_serializer(self.get_queryset().get(pk=user.pk)).data)
        if not is_active and user.deliveries.exclude(status__in=["delivered", "cancelled"]).exists():
            raise ValidationError("Kuryerning faol buyurtmalari bor. Avval ularni boshqa kuryerga tayinlang yoki yakunlang.")
        user.is_active = is_active
        user.save(update_fields=["is_active"])
        Token.objects.filter(user=user).delete()
        return Response(self.get_serializer(self.get_queryset().get(pk=user.pk)).data)


@api_view(["GET"])
@permission_classes([IsDeliveryAdmin])
def dashboard(request):
    today = Order.objects.filter(created_at__date=timezone.localdate())
    return Response({
        "today_orders": today.count(),
        "active_orders": Order.objects.exclude(status__in=["delivered", "cancelled"]).count(),
        "revenue": today.filter(status="delivered").aggregate(value=Sum("total"))["value"] or 0,
        "couriers": User.objects.filter(role="courier", is_active=True).count(),
        "statuses": list(Order.objects.values("status").annotate(count=Count("id"))),
    })
