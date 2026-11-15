from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings
from django.test.client import RequestFactory
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APITestCase

from .authentication import TelegramOnlyAuthentication
from .models import User
from .preview import PreviewApplication


@override_settings(ALLOWED_HOSTS=["preview.invalid"])
class PreviewFileTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        (root / "assets").mkdir()
        (root / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
        (root / "assets/app.js").write_text("window.ready=true", encoding="utf-8")
        (root / ".env").write_text("SECRET=hidden", encoding="utf-8")
        self.api_calls = []

        def application(environ, start_response):
            self.api_calls.append(environ["PATH_INFO"])
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b'{"ok":true}']

        self.application = PreviewApplication(application, root)

    def request(self, path, *, host="preview.invalid", secure=True):
        environ = RequestFactory().get(path, secure=secure, HTTP_HOST=host).environ
        response = {}

        def start_response(status, headers):
            response.update(status=int(status.split()[0]), headers=dict(headers))

        result = self.application(environ, start_response)
        try:
            response["body"] = b"".join(result)
        finally:
            if hasattr(result, "close"):
                result.close()
        return response

    def test_only_built_assets_and_api_are_served(self):
        self.assertEqual(self.request("/")["status"], 200)
        self.assertEqual(self.request("/assets/app.js")["status"], 200)
        self.assertEqual(self.request("/api/health/")["status"], 200)
        self.assertEqual(self.api_calls, ["/api/health/"])
        for path in ["/.env", "/admin/", "/src/App.jsx", "/assets/../.env", "/assets/app.js.map", "/backend/.env"]:
            self.assertEqual(self.request(path)["status"], 404)

    def test_http_and_wrong_host_are_rejected(self):
        self.assertEqual(self.request("/", secure=False)["status"], 400)
        self.assertEqual(self.request("/", host="wrong.invalid")["status"], 400)

    def test_frontend_can_be_embedded_in_telegram(self):
        response = self.request("/")
        self.assertNotIn("X-Frame-Options", response["headers"])
        self.assertEqual(response["headers"]["Cache-Control"], "no-cache")
        self.assertEqual(response["headers"]["X-Content-Type-Options"], "nosniff")

    def test_production_http_health_exception_is_limited_to_get_and_head(self):
        self.application.http_health_path = "/api/ready/"
        self.assertEqual(self.request("/api/ready/", secure=False)["status"], 200)
        for path in ["/", "/api/users/", "/api/health/"]:
            self.assertEqual(self.request(path, secure=False)["status"], 400)
        self.assertEqual(self.request("/api/ready/", host="wrong.invalid", secure=False)["status"], 400)

    def test_preview_does_not_allow_http_health_by_default(self):
        self.assertEqual(self.request("/api/ready/", secure=False)["status"], 400)


class PreviewAuthenticationTests(APITestCase):
    def test_local_demo_token_is_rejected_but_telegram_token_works(self):
        demo = User.objects.create_user(username="demo_admin", role="admin")
        real = User.objects.create_user(username="telegram", telegram_id=123456789)
        demo_token = Token.objects.create(user=demo)
        real_token = Token.objects.create(user=real)
        authentication = TelegramOnlyAuthentication()
        with self.assertRaises(AuthenticationFailed):
            authentication.authenticate_credentials(demo_token.key)
        self.assertEqual(authentication.authenticate_credentials(real_token.key)[0], real)
