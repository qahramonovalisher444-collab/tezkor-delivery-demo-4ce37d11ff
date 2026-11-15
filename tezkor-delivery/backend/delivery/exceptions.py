from rest_framework.exceptions import APIException


class OrderRequestConflict(APIException):
    status_code = 409
    default_detail = "Bu so‘rov raqami bilan boshqa buyurtma allaqachon yaratilgan."
    default_code = "order_request_conflict"
