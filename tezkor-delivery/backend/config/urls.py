from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from delivery import views
from delivery.notification_views import NotificationViewSet
from delivery.webhook import telegram_webhook


router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("products", views.ProductViewSet, basename="product")
router.register("orders", views.OrderViewSet, basename="order")
router.register("users", views.UserViewSet, basename="user")
router.register("notifications", NotificationViewSet, basename="notification")
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", views.health),
    path("api/ready/", views.readiness),
    path("api/telegram/webhook/", telegram_webhook),
    path("api/config/", views.app_config),
    path("api/auth/telegram/", views.telegram_login),
    path("api/auth/demo/", views.demo_login),
    path("api/auth/logout/", views.logout),
    path("api/auth/me/", views.me),
    path("api/dashboard/", views.dashboard),
    path("api/", include(router.urls)),
]
