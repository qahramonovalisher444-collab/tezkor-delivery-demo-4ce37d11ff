from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import OperationalError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from config.deployment import production_options
from .models import Category, Order, Product, User


class ProductionConfigurationTests(SimpleTestCase):
    def setUp(self):
        self.environment = {
            "DJANGO_SECRET_KEY": "test-" + "a" * 64,
            "DATABASE_URL": "postgresql://user:password@database/tezkor",
            "RENDER_EXTERNAL_URL": "https://example.onrender.com",
            "RENDER_EXTERNAL_HOSTNAME": "example.onrender.com",
            "BOT_TOKEN": "test-token", "TELEGRAM_ADMIN_IDS": "123456789",
            "DJANGO_DEBUG": "true", "ENABLE_DEMO_AUTH": "true",
        }

    def test_production_forces_secure_settings_and_exact_host(self):
        values = production_options(self.environment)
        self.assertFalse(values["DEBUG"])
        self.assertFalse(values["ENABLE_DEMO_AUTH"])
        self.assertEqual(values["WEBAPP_URL"], "https://example.onrender.com")
        self.assertEqual(values["ALLOWED_HOSTS"], ["example.onrender.com"])
        self.assertTrue(values["SESSION_COOKIE_SECURE"])
        self.assertEqual(values["SECURE_REDIRECT_EXEMPT"], [r"^api/ready/$"])

    def test_custom_domain_preserves_render_healthcheck_host(self):
        values = production_options({**self.environment, "WEBAPP_URL": "https://food.example.uz/"})
        self.assertEqual(values["ALLOWED_HOSTS"], ["food.example.uz", "example.onrender.com"])
        self.assertEqual(values["CSRF_TRUSTED_ORIGINS"], ["https://food.example.uz"])

    def test_insecure_or_non_origin_webapp_urls_are_rejected(self):
        for origin in ["http://example.test", "https://example.test/path", "https://user:pass@example.test", "https://example.test?token=x", "https://example.test:443"]:
            with self.subTest(origin=origin), self.assertRaises(ImproperlyConfigured):
                production_options({**self.environment, "WEBAPP_URL": origin})

    def test_database_must_be_persistent_postgres(self):
        for database in ["", "sqlite:///db.sqlite3", "postgresql://localhost/"]:
            with self.subTest(database=database), self.assertRaises(ImproperlyConfigured):
                production_options({**self.environment, "DATABASE_URL": database})

    def test_placeholder_secret_is_rejected(self):
        for secret in ["", "short", "replace-with-a-long-random-secret", "local-development-only-change-before-deployment"]:
            with self.subTest(secret=secret), self.assertRaises(ImproperlyConfigured):
                production_options({**self.environment, "DJANGO_SECRET_KEY": secret})

    def test_missing_bot_token_and_invalid_admin_ids_are_rejected(self):
        for values in [{"BOT_TOKEN": ""}, {"TELEGRAM_ADMIN_IDS": ""}, {"TELEGRAM_ADMIN_IDS": "-1"}, {"TELEGRAM_ADMIN_IDS": "name"}]:
            with self.subTest(values=values), self.assertRaises(ImproperlyConfigured):
                production_options({**self.environment, **values})

    def test_host_wildcards_and_proxy_injection_are_rejected(self):
        for host in ["*", "https://app.onrender.com", "app.onrender.com:443", "evil.test"]:
            with self.subTest(host=host), self.assertRaises(ImproperlyConfigured):
                production_options({**self.environment, "RENDER_EXTERNAL_HOSTNAME": host})


class ReadinessTests(APITestCase):
    def test_database_ready_is_public_without_authentication(self):
        response = self.client.get("/api/ready/", HTTP_AUTHORIZATION="Token invalid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})

    def test_database_failure_returns_unavailable_without_private_error(self):
        with patch("delivery.views.connection.cursor", side_effect=OperationalError("private database credentials")):
            response = self.client.get("/api/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"status": "unavailable"})

    def test_readiness_does_not_accept_post(self):
        self.assertEqual(self.client.post("/api/ready/", {}).status_code, 405)


@override_settings(DEBUG=False)
class ProductionMenuTests(APITestCase):
    def test_menu_seed_creates_no_demo_accounts_or_orders(self):
        call_command("seed_menu", stdout=StringIO())
        self.assertEqual(Product.objects.count(), 9)
        self.assertEqual(Category.objects.count(), 5)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)
        self.assertTrue(all(product.image_url.startswith("/menu/") for product in Product.objects.all()))

    def test_existing_catalog_is_not_recreated_or_overwritten(self):
        call_command("seed_menu", stdout=StringIO())
        product = Product.objects.first()
        product.price = 1000
        product.save(update_fields=["price"])
        Product.objects.exclude(pk=product.pk).first().delete()
        call_command("seed_menu", stdout=StringIO())
        product.refresh_from_db()
        self.assertEqual(product.price, 1000)
        self.assertEqual(Product.objects.count(), 8)
