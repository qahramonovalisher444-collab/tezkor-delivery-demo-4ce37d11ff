import json
import math
import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .settings import *


preview_url = urlsplit(os.getenv("TELEGRAM_PREVIEW_URL", ""))
if preview_url.scheme != "https" or not preview_url.hostname or preview_url.username or preview_url.password or preview_url.port or preview_url.path not in {"", "/"} or preview_url.query or preview_url.fragment:
    raise ImproperlyConfigured("TELEGRAM_PREVIEW_URL haqiqiy HTTPS origin bo‘lishi kerak.")
if SECRET_KEY == "local-development-only-change-before-deployment":
    raise ImproperlyConfigured("Telegram rejimida alohida DJANGO_SECRET_KEY talab qilinadi.")
DEBUG = False
ENABLE_DEMO_AUTH = False
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_AUTHENTICATION_CLASSES": ["delivery.authentication.TelegramOnlyAuthentication"]}
ALLOWED_HOSTS = [preview_url.hostname]
CORS_ALLOWED_ORIGINS = [f"https://{preview_url.hostname}"]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 86400
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
WEBAPP_URL = f"https://{preview_url.hostname}"
if os.getenv("TELEGRAM_AUTH_CLOCK"):
    try:
        clock = json.loads(os.environ["TELEGRAM_AUTH_CLOCK"])
        if not isinstance(clock, list) or len(clock) != 2 or any(type(value) not in {int, float} or not math.isfinite(value) for value in clock):
            raise ValueError
        TELEGRAM_AUTH_CLOCK = tuple(clock)
    except (TypeError, ValueError):
        raise ImproperlyConfigured("Telegram kirish vaqti uchun tayanch yaroqsiz.") from None
