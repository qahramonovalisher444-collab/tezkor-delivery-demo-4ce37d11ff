from pathlib import Path, PurePosixPath

from django.core.exceptions import DisallowedHost
from django.core.handlers.wsgi import WSGIRequest
from whitenoise import WhiteNoise


def not_found(environ, start_response):
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8"), ("X-Content-Type-Options", "nosniff")])
    return [b"Not found"]


class PreviewApplication:
    def __init__(self, application, directory, http_health_path=None):
        self.application = application
        self.http_health_path = http_health_path
        self.directory = Path(directory).resolve()
        if not (self.directory / "index.html").is_file():
            raise RuntimeError("React build topilmadi. Avval frontend buildni bajaring.")
        self.static = WhiteNoise(not_found, root=str(self.directory), index_file=True, max_age=3600, add_headers_function=self.static_headers)

    @staticmethod
    def static_headers(headers, path, url):
        headers["X-Content-Type-Options"] = "nosniff"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Strict-Transport-Security"] = "max-age=86400"
        if url in {"/", "/index.html"}:
            headers["Cache-Control"] = "no-cache"

    def __call__(self, environ, start_response):
        try:
            WSGIRequest(environ).get_host()
        except DisallowedHost:
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [b"Invalid host"]
        is_health_probe = self.http_health_path is not None and environ.get("PATH_INFO") == self.http_health_path and environ.get("REQUEST_METHOD") in {"GET", "HEAD"}
        if environ.get("wsgi.url_scheme") != "https" and not is_health_probe:
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [b"HTTPS required"]
        path = environ.get("PATH_INFO", "/")
        if path.startswith("/api/"):
            return self.application(environ, start_response)
        parts = PurePosixPath(path).parts
        allowed_asset = (path.startswith("/assets/") or path.startswith("/menu/")) and not any(part.startswith(".") for part in parts) and PurePosixPath(path).suffix in {".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf"}
        if environ.get("REQUEST_METHOD") in {"GET", "HEAD"} and (path in {"/", "/index.html", "/favicon.svg"} or allowed_asset):
            return self.static(environ, start_response)
        return not_found(environ, start_response)
