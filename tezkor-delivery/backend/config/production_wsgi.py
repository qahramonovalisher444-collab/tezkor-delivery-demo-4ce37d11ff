import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.production")
django_application = get_wsgi_application()

from delivery.preview import PreviewApplication

application = PreviewApplication(django_application, settings.FRONTEND_BUILD_DIR, http_health_path="/api/ready/")
