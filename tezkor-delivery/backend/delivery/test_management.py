from datetime import datetime, timezone as datetime_timezone

from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Category, Order, OrderItem, Product, User


class ManagementAPITests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="manager", role="admin")
        self.customer = User.objects.create_user(username="customer", first_name="Aziz", last_name="Karimov", role="customer", telegram_id=123456789)
        self.other_customer = User.objects.create_user(username="other_customer", first_name="Madina", role="customer")
        self.courier = User.objects.create_user(username="courier", first_name="Sardor", role="courier")
        self.category = Category.objects.create(name="Burgerlar", icon="burger", position=1)
        self.product = Product.objects.create(name="Klassik burger", category=self.category, price=35000)
        self.client.force_authenticate(self.admin_user)

    def make_order(self, customer=None, courier=None, status="pending", address="Toshkent, Navoiy 12"):
        order = Order.objects.create(customer=customer or self.customer, courier=courier, status=status, address=address, phone="+998901234567", subtotal=35000, delivery_fee=10000, total=45000)
        OrderItem.objects.create(order=order, product=self.product, product_name=self.product.name, unit_price=self.product.price, quantity=1)
        return order

    def test_product_image_accepts_local_menu_or_https_but_rejects_other_paths(self):
        for image in ["/menu/classic-burger.jpg", "https://example.com/food.jpg", ""]:
            response = self.client.patch(f"/api/products/{self.product.pk}/", {"image_url": image})
            self.assertEqual(response.status_code, 200, response.data)
        for image in ["/backend/.env", "/menu/../secret.jpg", "javascript:alert(1)"]:
            self.assertEqual(self.client.patch(f"/api/products/{self.product.pk}/", {"image_url": image}).status_code, 400)

    def test_category_create_edit_reorder_and_delete_empty(self):
        response = self.client.post("/api/categories/", {"name": "Ichimliklar", "icon": "drink", "position": 0})
        self.assertEqual(response.status_code, 201, response.data)
        category_id = response.data["id"]
        self.assertEqual(self.client.get("/api/categories/").data[0]["id"], category_id)
        response = self.client.patch(f"/api/categories/{category_id}/", {"name": "Yangi ichimliklar", "position": 5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/categories/").data[-1]["name"], "Yangi ichimliklar")
        self.assertEqual(self.client.delete(f"/api/categories/{category_id}/").status_code, 204)
        self.assertFalse(Category.objects.filter(pk=category_id).exists())

    def test_category_with_hidden_product_cannot_be_deleted(self):
        self.product.is_available = False
        self.product.save()
        self.assertEqual(self.client.get(f"/api/categories/{self.category.id}/").data["product_count"], 1)
        self.assertEqual(self.client.delete(f"/api/categories/{self.category.id}/").status_code, 400)
        self.assertTrue(Category.objects.filter(pk=self.category.id).exists())
        self.assertTrue(Product.objects.filter(pk=self.product.id).exists())

    def test_category_inputs_and_non_admin_writes_rejected(self):
        for invalid in [{"position": -1}, {"position": 10001}, {"icon": "unknown"}, {"name": ""}]:
            self.assertEqual(self.client.patch(f"/api/categories/{self.category.id}/", invalid).status_code, 400)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post("/api/categories/", {"name": "Yangi"}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/categories/{self.category.id}/").status_code, 403)
        self.assertEqual(self.client.post(f"/api/users/{self.courier.id}/activity/", {"is_active": False}).status_code, 403)

    def test_block_revokes_token_and_unblock_does_not_restore_old_token(self):
        token = Token.objects.create(user=self.customer).key
        response = self.client.post(f"/api/users/{self.customer.id}/activity/", {"is_active": False})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["is_active"])
        self.assertFalse(Token.objects.filter(key=token).exists())
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.client.credentials()
        self.client.force_authenticate(self.admin_user)
        response = self.client.post(f"/api/users/{self.customer.id}/activity/", {"is_active": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_active"])
        self.assertFalse(Token.objects.filter(key=token).exists())

    @override_settings(TELEGRAM_ADMIN_IDS={987654321}, ENABLE_DEMO_AUTH=True)
    def test_protected_accounts_cannot_be_blocked_or_demoted(self):
        owner = User.objects.create_user(username="owner", telegram_id=987654321, role="admin")
        superuser = User.objects.create_superuser(username="root", password="test-password-only")
        demo = User.objects.create_user(username="demo_courier", role="courier")
        protected = [self.admin_user, owner, superuser, demo]
        users = {user["id"]: user for user in self.client.get("/api/users/").data}
        for target in protected:
            self.assertFalse(users[target.id]["can_manage"])
            self.assertEqual(self.client.post(f"/api/users/{target.id}/activity/", {"is_active": False}).status_code, 400)
            self.assertEqual(self.client.post(f"/api/users/{target.id}/role/", {"role": "customer"}).status_code, 400)
            target.refresh_from_db()
            self.assertTrue(target.is_active)

    def test_active_courier_is_protected_until_deliveries_finish(self):
        active = self.make_order(courier=self.courier, status="ready")
        self.make_order(courier=self.courier, status="delivered")
        self.make_order(courier=self.courier, status="cancelled")
        response = self.client.get(f"/api/users/{self.courier.id}/")
        self.assertEqual(response.data["active_deliveries"], 1)
        self.assertEqual(self.client.post(f"/api/users/{self.courier.id}/activity/", {"is_active": False}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/users/{self.courier.id}/role/", {"role": "customer"}).status_code, 400)
        active.status = "delivered"
        active.save(update_fields=["status"])
        response = self.client.post(f"/api/users/{self.courier.id}/activity/", {"is_active": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active_deliveries"], 0)

    def test_blocked_courier_cannot_be_assigned(self):
        order = self.make_order()
        self.client.post(f"/api/users/{self.courier.id}/activity/", {"is_active": False})
        self.assertEqual(self.client.post(f"/api/orders/{order.id}/assign/", {"courier": self.courier.id}).status_code, 400)
        self.client.post(f"/api/users/{self.courier.id}/activity/", {"is_active": True})
        self.assertEqual(self.client.post(f"/api/orders/{order.id}/assign/", {"courier": self.courier.id}).status_code, 200)
        self.assertEqual(self.client.get(f"/api/users/{self.courier.id}/").data["active_deliveries"], 1)

    def test_active_customer_role_cannot_hide_their_order(self):
        order = self.make_order()
        self.assertEqual(self.client.post(f"/api/users/{self.customer.id}/role/", {"role": "courier"}).status_code, 400)
        order.status = "cancelled"
        order.save(update_fields=["status"])
        token = Token.objects.create(user=self.customer)
        self.assertEqual(self.client.post(f"/api/users/{self.customer.id}/role/", {"role": "courier"}).status_code, 200)
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_no_op_role_and_activity_preserve_session_and_workload(self):
        self.make_order(courier=self.courier, status="ready")
        token = Token.objects.create(user=self.courier)
        response = self.client.post(f"/api/users/{self.courier.id}/role/", {"role": "courier"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active_deliveries"], 1)
        response = self.client.post(f"/api/users/{self.courier.id}/activity/", {"is_active": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active_deliveries"], 1)
        self.assertTrue(Token.objects.filter(pk=token.pk).exists())

    def test_user_search_role_and_blocked_filters(self):
        self.courier.is_active = False
        self.courier.save(update_fields=["is_active"])
        response = self.client.get("/api/users/", {"role": "courier", "is_active": "false"})
        self.assertEqual([user["id"] for user in response.data], [self.courier.id])
        for search in ["Aziz Karimov", "123456789"]:
            response = self.client.get("/api/users/", {"search": search})
            self.assertEqual([user["id"] for user in response.data], [self.customer.id])
        self.assertEqual(self.client.get("/api/users/", {"role": "invalid"}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/users/{self.customer.id}/activity/", {}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/users/{self.customer.id}/activity/", {"is_active": "invalid"}).status_code, 400)

    def test_search_by_id_full_name_phone_address_and_food(self):
        order = self.make_order(address="Toshkent, Bobur 45")
        for search in [f"#{order.id:04d}", "Aziz Karimov", "+998 (90) 123-45-67", "Bobur", "burger"]:
            response = self.client.get("/api/orders/", {"search": search})
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual([item["id"] for item in response.data], [order.id])
        OrderItem.objects.create(order=order, product=self.product, product_name="Double burger", unit_price=35000, quantity=1)
        self.assertEqual(len(self.client.get("/api/orders/", {"search": "burger"}).data), 1)

    def test_search_filters_do_not_leak_other_customers_or_couriers_orders(self):
        own = self.make_order(courier=self.courier)
        other = self.make_order(customer=self.other_customer)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get("/api/orders/", {"search": f"#{other.id}"}).data, [])
        self.assertEqual([order["id"] for order in self.client.get("/api/orders/", {"search": "burger"}).data], [own.id])
        self.client.force_authenticate(self.courier)
        self.assertEqual(self.client.get("/api/orders/", {"search": f"#{other.id}"}).data, [])

    def test_order_date_filter_uses_restaurant_timezone_and_inclusive_bounds(self):
        previous = self.make_order()
        following = self.make_order()
        Order.objects.filter(pk=previous.pk).update(created_at=datetime(2026, 11, 14, 18, 59, tzinfo=datetime_timezone.utc))
        Order.objects.filter(pk=following.pk).update(created_at=datetime(2026, 11, 14, 19, 1, tzinfo=datetime_timezone.utc))
        response = self.client.get("/api/orders/", {"date_from": "2026-11-15", "date_to": "2026-11-15"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([order["id"] for order in response.data], [following.id])

    def test_invalid_order_filters_rejected_and_huge_search_is_safe(self):
        for filters in [{"date_from": "invalid"}, {"date_from": "2026-11-15", "date_to": "2026-11-14"}, {"status": "unknown"}, {"search": "x" * 121}]:
            self.assertEqual(self.client.get("/api/orders/", filters).status_code, 400)
        self.assertEqual(self.client.get("/api/orders/", {"search": "9" * 120}).status_code, 200)
        active = self.make_order()
        self.make_order(status="delivered")
        self.assertEqual([order["id"] for order in self.client.get("/api/orders/", {"status": "active"}).data], [active.id])
