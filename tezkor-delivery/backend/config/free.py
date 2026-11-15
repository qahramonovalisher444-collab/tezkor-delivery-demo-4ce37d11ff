import os
import re

from django.core.exceptions import ImproperlyConfigured

from .production import *


TELEGRAM_WEBHOOK_ENABLED = os.getenv("TELEGRAM_WEBHOOK_ENABLED", "false").lower() == "true"
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", TELEGRAM_WEBHOOK_SECRET):
    raise ImproperlyConfigured("Bepul hosting uchun uzun TELEGRAM_WEBHOOK_SECRET kerak.")
