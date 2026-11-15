import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import patch
from urllib.parse import urlencode

from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Category, Order, OrderEvent, OrderNotification, Product, User


class DeliveryAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="customer", role="customer")
        self.other_customer = User.objects.create_user(username="other", role="customer")
        self.courier = User.objects.create_user(username="courier", role="courier")
        self.other_courier = User.objects.create_user(username="other_courier", role="courier")
        self.admin_user = User.objects.create_user(username="manager", role="admin")
        self.category = Category.objects.create(name="Burgerlar")
        self.product = Product.objects.create(category=self.category, name="Burger", price=35000)
        self.payload = {"items": [{"product": self.product.id, "quantity": 2}], "phone": "+998 90 123 45 67", "address": "Toshkent, Navoiy ko‘chasi 12"}
        self.client.force_authenticate(self.customer)

    def create_order(self):
        response = self.client.post("/api/orders/", self.payload)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    @override_settings(DELIVERY_FEE=10000)
    def test_prices_are_server_calculated_and_snapshotted(self):
        self.payload.update({"total": 1, "delivery_fee": 0, "customer": self.other_customer.id, "status": "delivered"})
        order_id = self.create_order()
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.total, 80000)
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.status, "pending")
        self.product.price = 60000
        self.product.name = "New name"
        self.product.save()
        self.assertEqual(order.items.get().unit_price, 35000)
        self.assertEqual(order.items.get().product_name, "Burger")

    def test_customers_cannot_read_other_orders(self):
        order_id = self.create_order()
        self.client.force_authenticate(self.other_customer)
        self.assertEqual(self.client.get("/api/orders/").data, [])
        self.assertEqual(self.client.get(f"/api/orders/{order_id}/").status_code, 404)

    def test_customer_cannot_manage_products_users_or_assign(self):
        order_id = self.create_order()
        self.assertEqual(self.client.patch(f"/api/products/{self.product.id}/", {"price": 1}).status_code, 403)
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/assign/", {"courier": self.courier.id}).status_code, 403)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/status/", {"status": "confirmed"}).status_code, 403)

    def test_customer_can_only_cancel_pending_order(self):
        order_id = self.create_order()
        response = self.client.post(f"/api/orders/{order_id}/status/", {"status": "cancelled"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OrderEvent.objects.filter(order_id=order_id).count(), 2)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/status/", {"status": "pending"}).status_code, 403)

    def test_full_order_lifecycle_and_courier_isolation(self):
        order_id = self.create_order()
        self.client.force_authenticate(self.admin_user)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/status/", {"status": "delivered"}).status_code, 400)
        for next_status in ["confirmed", "preparing", "ready"]:
            self.assertEqual(self.client.post(f"/api/orders/{order_id}/status/", {"status": next_status}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/status/", {"status": "delivering"}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/assign/", {"courier": self.customer.id}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/orders/{order_id}/assign/", {"courier": self.courier.id}).status_code, 200)
        self.client.force_authenticate(self.other_courier)
        self.assertEqual(self.client.get(f"/api/orders/{order_id}/").status_code, 404)
        self.client.force_authenticate(self.courier)
        for next_status in ["delivering", "delivered"]:
            self.assertEqual(self.client.post(f"/api/orders/{order_id}/status/", {"status": next_status}).status_code, 200)
        self.assertEqual(OrderEvent.objects.filter(order_id=order_id).count(), 6)
        self.assertEqual(self.client.post("/api/orders/", self.payload).status_code, 403)

    def test_unavailable_duplicate_empty_and_invalid_quantity_rejected(self):
        for items in [[], [{"product": self.product.id, "quantity": 0}], [{"product": self.product.id, "quantity": 31}], self.payload["items"] * 2]:
            self.assertEqual(self.client.post("/api/orders/", {**self.payload, "items": items}).status_code, 400)
        self.product.is_available = False
        self.product.save()
        self.assertEqual(self.client.post("/api/orders/", self.payload).status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_admin_cannot_change_own_role_or_active_courier_role(self):
        order_id = self.create_order()
        self.client.force_authenticate(self.admin_user)
        self.client.post(f"/api/orders/{order_id}/assign/", {"courier": self.courier.id})
        self.assertEqual(self.client.post(f"/api/users/{self.admin_user.id}/role/", {"role": "customer"}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/users/{self.courier.id}/role/", {"role": "customer"}).status_code, 400)

    @override_settings(ENABLE_DEMO_AUTH=False)
    def test_demo_login_disabled(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post("/api/auth/demo/", {"role": "admin"}).status_code, 403)

    def test_public_menu_but_private_orders(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/products/").status_code, 200)
        self.assertEqual(self.client.get("/api/orders/").status_code, 401)

    def test_product_negative_price_rejected(self):
        self.client.force_authenticate(self.admin_user)
        self.assertEqual(self.client.patch(f"/api/products/{self.product.id}/", {"price": -1}).status_code, 400)


@override_settings(BOT_TOKEN="12345:test-token", TELEGRAM_ADMIN_IDS=set())
class TelegramAuthTests(APITestCase):
    def signed_data(self, age=0, telegram_user=None, **extra):
        fields = {"auth_date": str(int(time.time()) - age), "user": json.dumps(telegram_user or {"id": 123456789, "first_name": "Aziz"}), **extra}
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret = hmac.new(b"WebAppData", b"12345:test-token", hashlib.sha256).digest()
        fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        return urlencode(fields)

    def test_valid_signature_and_no_role_escalation(self):
        response = self.client.post("/api/auth/telegram/", {"init_data": self.signed_data(telegram_user={"id": 123456789, "first_name": "Aziz", "role": "admin"}), "role": "admin"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["user"]["role"], "customer")
        self.assertFalse(User.objects.get(telegram_id=123456789).has_usable_password())

    def test_expired_future_tampered_and_duplicate_data_rejected(self):
        for init_data in [self.signed_data(age=4000), self.signed_data(age=-300), self.signed_data().replace("Aziz", "Admin"), self.signed_data() + "&auth_date=1", "", self.signed_data(telegram_user={"id": "123", "first_name": "Aziz"})]:
            self.assertEqual(self.client.post("/api/auth/telegram/", {"init_data": init_data}).status_code, 401)

    def test_signature_field_included_in_hmac(self):
        response = self.client.post("/api/auth/telegram/", {"init_data": self.signed_data(signature="telegram-ed25519-signature")})
        self.assertEqual(response.status_code, 200)

    @override_settings(TELEGRAM_AUTH_CLOCK=(1700000000, 1000))
    def test_verified_clock_accepts_fresh_data_with_wrong_local_time(self):
        with patch("delivery.telegram.time.time", return_value=1700000010):
            init_data = self.signed_data()
        for local_time in [1700007210, 1699992810]:
            with patch("delivery.telegram.time.time", return_value=local_time), patch("delivery.telegram.time.monotonic", return_value=1010):
                response = self.client.post("/api/auth/telegram/", {"init_data": init_data})
            self.assertEqual(response.status_code, 200, response.data)

    @override_settings(TELEGRAM_AUTH_CLOCK=(1700000000, 1000))
    def test_verified_clock_still_rejects_expired_and_future_data(self):
        with patch("delivery.telegram.time.time", return_value=1700000010):
            samples = [self.signed_data(age=4000), self.signed_data(age=-300)]
        with patch("delivery.telegram.time.monotonic", return_value=1010):
            for init_data in samples:
                self.assertEqual(self.client.post("/api/auth/telegram/", {"init_data": init_data}).status_code, 401)

    @override_settings(TELEGRAM_AUTH_CLOCK=(1700000000, 1000))
    def test_verified_clock_does_not_bypass_signature_or_owner_check(self):
        with patch("delivery.telegram.time.time", return_value=1700000010):
            init_data = self.signed_data().replace("Aziz", "Admin")
        with patch("delivery.telegram.time.monotonic", return_value=1010):
            self.assertEqual(self.client.post("/api/auth/telegram/", {"init_data": init_data}).status_code, 401)
        self.assertFalse(User.objects.filter(telegram_id=123456789).exists())

    @override_settings(TELEGRAM_AUTH_CLOCK=(1700000000, 1000))
    def test_verified_clock_expires_data_even_if_local_clock_moves_back(self):
        with patch("delivery.telegram.time.time", return_value=1700000000):
            init_data = self.signed_data()
        with patch("delivery.telegram.time.time", return_value=1699990000), patch("delivery.telegram.time.monotonic", return_value=5001):
            self.assertEqual(self.client.post("/api/auth/telegram/", {"init_data": init_data}).status_code, 401)

    def test_blocked_user_cannot_login(self):
        User.objects.create_user(username="blocked", telegram_id=123456789, is_active=False)
        self.assertEqual(self.client.post("/api/auth/telegram/", {"init_data": self.signed_data()}).status_code, 403)

    def test_login_keeps_edited_profile_and_saved_address(self):
        User.objects.create_user(username="existing", telegram_id=123456789, first_name="Edited name", phone="+998901112233", default_address="Toshkent, Navoiy 12")
        response = self.client.post("/api/auth/telegram/", {"init_data": self.signed_data()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["first_name"], "Edited name")
        self.assertEqual(response.data["user"]["default_address"], "Toshkent, Navoiy 12")

    @override_settings(TELEGRAM_ADMIN_IDS={987654321})
    def test_only_verified_configured_id_gets_admin_role(self):
        response = self.client.post("/api/auth/telegram/", {"init_data": self.signed_data(telegram_user={"id": 987654321, "first_name": "Admin"})})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "admin")
        response = self.client.post("/api/auth/telegram/", {"init_data": self.signed_data()})
        self.assertEqual(response.data["user"]["role"], "customer")


class CheckoutAndProfileTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="buyer", first_name="Aziz", role="customer")
        self.other_customer = User.objects.create_user(username="another_buyer", role="customer")
        self.category = Category.objects.create(name="Taomlar")
        self.product = Product.objects.create(category=self.category, name="Burger", price=35000)
        self.payload = {"request_id": str(uuid.uuid4()), "items": [{"product": self.product.id, "quantity": 1}], "address": "Toshkent, Navoiy 12", "phone": "+998 90 123 45 67", "save_details": True}
        self.client.force_authenticate(self.customer)

    def test_profile_updates_only_own_editable_fields(self):
        response = self.client.patch("/api/auth/me/", {"first_name": "Madina", "last_name": "Aliyeva", "phone": "+998 (90) 111-22-33", "default_address": "Toshkent, Bobur 15", "role": "admin", "is_active": False, "username": "spoofed", "telegram_id": 999, "id": self.other_customer.id})
        self.assertEqual(response.status_code, 200, response.data)
        self.customer.refresh_from_db()
        self.other_customer.refresh_from_db()
        self.assertEqual(self.customer.role, "customer")
        self.assertTrue(self.customer.is_active)
        self.assertEqual(self.customer.username, "buyer")
        self.assertIsNone(self.customer.telegram_id)
        self.assertEqual(self.customer.phone, "+998901112233")
        self.assertEqual(response.data["name"], "Madina Aliyeva")
        self.assertEqual(response.data["default_address"], "Toshkent, Bobur 15")
        self.assertEqual(self.other_customer.first_name, "")

    def test_invalid_profile_is_rejected_without_partial_update(self):
        response = self.client.patch("/api/auth/me/", {"first_name": "Changed", "phone": "123", "default_address": "abc"})
        self.assertEqual(response.status_code, 400)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Aziz")

    def test_profile_details_can_be_cleared(self):
        self.customer.phone = "+998901112233"
        self.customer.default_address = "Toshkent, Bobur 15"
        self.customer.save()
        response = self.client.patch("/api/auth/me/", {"phone": "", "default_address": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["phone"], "")
        self.assertEqual(response.data["default_address"], "")

    def test_anonymous_cannot_edit_profile(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch("/api/auth/me/", {"first_name": "Changed"}).status_code, 401)

    def test_checkout_saves_details_only_with_consent(self):
        response = self.client.post("/api/orders/", {**self.payload, "save_details": False})
        self.assertEqual(response.status_code, 201, response.data)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "")
        self.assertEqual(self.customer.default_address, "")
        response = self.client.post("/api/orders/", {**self.payload, "request_id": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 201, response.data)
        self.customer.refresh_from_db()
        profile = self.client.get("/api/auth/me/").data
        self.assertEqual(profile["phone"], "+998901234567")
        self.assertEqual(profile["default_address"], self.payload["address"])

    def test_invalid_checkout_does_not_save_profile(self):
        self.product.is_available = False
        self.product.save()
        self.assertEqual(self.client.post("/api/orders/", self.payload).status_code, 400)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.default_address, "")
        self.assertEqual(Order.objects.count(), 0)

    def test_retry_returns_original_order_and_enqueues_once(self):
        self.customer.telegram_id = 123456789
        self.customer.save(update_fields=["telegram_id"])
        with patch("delivery.notifications.bot_request") as sender:
            first = self.client.post("/api/orders/", self.payload)
            self.assertEqual(first.status_code, 201, first.data)
            self.product.price = 55000
            self.product.is_available = False
            self.product.save()
            second = self.client.post("/api/orders/", self.payload)
            self.assertEqual(second.status_code, 200, second.data)
            self.assertEqual(first.data["id"], second.data["id"])
            self.assertEqual(first.data["total"], second.data["total"])
            self.assertEqual(Order.objects.count(), 1)
            self.assertEqual(OrderEvent.objects.count(), 1)
            self.assertEqual(OrderNotification.objects.count(), 1)
            sender.assert_not_called()

    def test_same_request_id_with_changed_cart_or_address_conflicts(self):
        self.assertEqual(self.client.post("/api/orders/", self.payload).status_code, 201)
        for changed in [{"address": "Toshkent, boshqa manzil 25"}, {"items": [{"product": self.product.id, "quantity": 2}]}]:
            response = self.client.post("/api/orders/", {**self.payload, **changed})
            self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(Order.objects.count(), 1)

    def test_request_ids_are_scoped_to_customer(self):
        first = self.client.post("/api/orders/", self.payload)
        self.client.force_authenticate(self.other_customer)
        second = self.client.post("/api/orders/", self.payload)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.data["id"], second.data["id"])
        self.assertEqual(Order.objects.count(), 2)

    def test_invalid_request_id_is_rejected(self):
        self.assertEqual(self.client.post("/api/orders/", {**self.payload, "request_id": "invalid"}).status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_order_contact_does_not_expose_account_or_default_address(self):
        response = self.client.post("/api/orders/", self.payload)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(set(response.data["customer"]), {"id", "name", "phone"})

    def test_retry_accepts_same_items_in_different_order(self):
        another_product = Product.objects.create(category=self.category, name="Fri", price=18000)
        self.payload["items"].append({"product": another_product.id, "quantity": 2})
        first = self.client.post("/api/orders/", self.payload)
        second = self.client.post("/api/orders/", {**self.payload, "items": list(reversed(self.payload["items"]))})
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["id"], second.data["id"])
