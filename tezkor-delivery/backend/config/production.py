import os

from .settings import *
from .deployment import production_options


globals().update(production_options(os.environ))
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_AUTHENTICATION_CLASSES": ["delivery.authentication.TelegramOnlyAuthentication"]}
FRONTEND_BUILD_DIR = os.getenv("FRONTEND_BUILD_DIR", "/app/frontend-dist")
