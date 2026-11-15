from decimal import Decimal
import uuid

from django.db import IntegrityError, transaction
from rest_framework.test import APITestCase

from .models import Category, Order, Product, User


class DeliveryMapTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="map_customer")
        self.other = User.objects.create_user(username="other_customer")
        self.courier = User.objects.create_user(username="map_courier", role="courier")
        category = Category.objects.create(name="Taomlar")
        product = Product.objects.create(category=category, name="Burger", price=35000)
        self.payload = {"request_id": str(uuid.uuid4()), "items": [{"product": product.pk, "quantity": 1}], "address": "Toshkent, Navoiy 12", "phone": "+998901234567", "delivery_latitude": "41.311081", "delivery_longitude": "69.240562"}
        self.client.force_authenticate(self.customer)

    def test_selected_point_is_saved_and_returned(self):
        response = self.client.post("/api/orders/", self.payload)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["delivery_latitude"], "41.311081")
        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.delivery_longitude, Decimal("69.240562"))
        self.assertEqual(order.address, self.payload["address"])

    def test_zero_coordinates_are_valid(self):
        response = self.client.post("/api/orders/", {**self.payload, "delivery_latitude": "0", "delivery_longitude": "0"})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["delivery_latitude"], "0.000000")

    def test_partial_out_of_range_and_nonfinite_points_are_rejected(self):
        for changes in [
            {"delivery_latitude": None}, {"delivery_longitude": None},
            {"delivery_latitude": "90.000001"}, {"delivery_latitude": "-90.000001"},
            {"delivery_longitude": "180.000001"}, {"delivery_longitude": "-180.000001"},
            {"delivery_latitude": "NaN"}, {"delivery_longitude": "Infinity"},
        ]:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/api/orders/", {**self.payload, **changes}).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_legacy_address_only_checkout_and_retry_still_work(self):
        payload = {key: value for key, value in self.payload.items() if not key.startswith("delivery_")}
        first = self.client.post("/api/orders/", payload)
        replay = self.client.post("/api/orders/", {**payload, "delivery_latitude": None, "delivery_longitude": None})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.data["id"], replay.data["id"])
        self.assertIsNone(first.data["delivery_latitude"])

    def test_different_map_point_cannot_reuse_request_id(self):
        first = self.client.post("/api/orders/", self.payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.client.post("/api/orders/", self.payload).status_code, 200)
        self.assertEqual(self.client.post("/api/orders/", {**self.payload, "delivery_latitude": "41.300000"}).status_code, 409)
        self.assertEqual(Order.objects.count(), 1)

    def test_coordinates_follow_customer_and_courier_access_permissions(self):
        created = self.client.post("/api/orders/", self.payload)
        order = Order.objects.get(pk=created.data["id"])
        endpoint = f"/api/orders/{order.pk}/"
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(endpoint).status_code, 404)
        self.client.force_authenticate(self.courier)
        self.assertEqual(self.client.get(endpoint).status_code, 404)
        order.courier = self.courier
        order.save(update_fields=["courier"])
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["delivery_longitude"], "69.240562")

    def test_database_rejects_partial_point_and_invalid_range(self):
        created = self.client.post("/api/orders/", self.payload)
        for changes in [{"delivery_latitude": None}, {"delivery_longitude": 181}]:
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                Order.objects.filter(pk=created.data["id"]).update(**changes)
