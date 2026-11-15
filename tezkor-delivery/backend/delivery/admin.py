from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Category, Order, OrderItem, OrderNotification, Product, User


@admin.register(User)
class DeliveryUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Delivery", {"fields": ("role", "telegram_id", "phone", "default_address")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Delivery", {"fields": ("role", "telegram_id", "phone", "default_address")}),)
    list_display = ["username", "first_name", "role", "telegram_id", "is_active"]
    list_filter = UserAdmin.list_filter + ("role",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "unit_price", "quantity"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "courier", "status", "total", "created_at"]
    list_filter = ["status", "created_at"]
    inlines = [OrderItemInline]
    readonly_fields = [field.name for field in Order._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "is_available"]
    list_filter = ["category", "is_available"]
    search_fields = ["name"]


@admin.register(OrderNotification)
class OrderNotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "event", "status", "attempts", "next_attempt_at", "sent_at"]
    list_filter = ["status"]
    readonly_fields = [field.name for field in OrderNotification._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Category)
