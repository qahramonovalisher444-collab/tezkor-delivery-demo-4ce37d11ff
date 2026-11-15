from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def production_options(environment):
    secret = environment.get("DJANGO_SECRET_KEY", "")
    if len(secret) < 32 or secret.startswith(("replace-", "local-development-")):
        raise ImproperlyConfigured("Production uchun tasodifiy uzun DJANGO_SECRET_KEY kerak.")
    database = environment.get("DATABASE_URL", "")
    try:
        parsed_database = urlsplit(database)
        if parsed_database.scheme not in {"postgres", "postgresql"} or not parsed_database.hostname or not parsed_database.path.strip("/"):
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured("Production DATABASE_URL PostgreSQL bazasiga yo‘naltirilishi kerak.") from None
    origin = environment.get("WEBAPP_URL") or environment.get("RENDER_EXTERNAL_URL", "")
    try:
        url = urlsplit(origin)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.port or url.path not in {"", "/"} or url.query or url.fragment:
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured("Production uchun HTTPS WEBAPP_URL kerak.") from None
    if not environment.get("BOT_TOKEN"):
        raise ImproperlyConfigured("Production uchun BOT_TOKEN kerak.")
    try:
        admin_ids = {int(value.strip()) for value in environment.get("TELEGRAM_ADMIN_IDS", "").split(",") if value.strip()}
        if not admin_ids or any(value <= 0 for value in admin_ids):
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured("TELEGRAM_ADMIN_IDS da haqiqiy raqamli ID kerak.") from None
    hosts = [url.hostname]
    render_host = environment.get("RENDER_EXTERNAL_HOSTNAME", "")
    if render_host:
        if not render_host.endswith(".onrender.com") or any(character in render_host for character in "/:@?#*"):
            raise ImproperlyConfigured("Render hostname yaroqsiz.")
        if render_host not in hosts:
            hosts.append(render_host)
    origin = f"https://{url.hostname}"
    return {
        "DEBUG": False, "ENABLE_DEMO_AUTH": False, "SECRET_KEY": secret,
        "WEBAPP_URL": origin, "ALLOWED_HOSTS": hosts, "TELEGRAM_ADMIN_IDS": admin_ids,
        "CORS_ALLOWED_ORIGINS": [origin], "CSRF_TRUSTED_ORIGINS": [origin],
        "SECURE_SSL_REDIRECT": True, "SESSION_COOKIE_SECURE": True, "CSRF_COOKIE_SECURE": True,
        "SECURE_HSTS_SECONDS": 31536000, "SECURE_REFERRER_POLICY": "strict-origin-when-cross-origin",
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SECURE_REDIRECT_EXEMPT": [r"^api/ready/$"],
    }
