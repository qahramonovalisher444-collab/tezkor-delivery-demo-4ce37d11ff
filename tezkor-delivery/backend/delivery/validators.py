import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_image_url(value):
    if re.fullmatch(r"/menu/[a-z0-9-]+\.(?:jpg|jpeg|png|webp|avif|svg)", value):
        return
    if value.startswith("/"):
        raise ValidationError("Rasm manzili /menu/ ichidagi fayl yoki HTTP(S) havola bo‘lsin.")
    URLValidator(schemes=["http", "https"])(value)
