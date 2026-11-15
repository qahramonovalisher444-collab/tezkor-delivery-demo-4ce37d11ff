from django.conf import settings
from rest_framework.permissions import BasePermission, SAFE_METHODS


def can_manage_user(actor, user):
    protected_demo = settings.ENABLE_DEMO_AUTH and user.username in {"demo_admin", "demo_courier", "demo_customer"}
    return bool(actor.is_authenticated and actor.is_delivery_admin and actor.pk != user.pk and not user.is_superuser and user.telegram_id not in settings.TELEGRAM_ADMIN_IDS and not protected_demo)


class IsDeliveryAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_delivery_admin)


class AdminOrReadOnly(IsDeliveryAdmin):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or super().has_permission(request, view)
