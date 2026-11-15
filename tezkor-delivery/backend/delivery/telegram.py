import hashlib
import hmac
import json
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl
from urllib.request import Request, urlopen

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed


class TelegramAPIError(RuntimeError):
    def __init__(self, code, retry_after=None):
        self.code = code if type(code) is int else 0
        self.retry_after = retry_after if type(retry_after) is int and retry_after > 0 else None
        super().__init__(f"Telegram API xatosi ({self.code}).")


def validate_init_data(init_data):
    if not settings.BOT_TOKEN:
        raise AuthenticationFailed("Telegram bot hali sozlanmagan.")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError
        received_hash = fields.pop("hash")
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            raise ValueError
        clock = settings.TELEGRAM_AUTH_CLOCK
        now = clock[0] + time.monotonic() - clock[1] if clock is not None else time.time()
        age = now - int(fields["auth_date"])
        if age < -30 or age > settings.TELEGRAM_AUTH_MAX_AGE:
            raise ValueError
        telegram_user = json.loads(fields["user"])
        telegram_id = telegram_user["id"]
        if type(telegram_id) is not int or not 0 < telegram_id < 2**52:
            raise ValueError
        return telegram_user
    except (ValueError, KeyError, TypeError):
        raise AuthenticationFailed("Telegram kirish ma’lumotlari yaroqsiz yoki eskirgan.") from None


def bot_request(method, payload, timeout=10):
    request = Request(
        f"https://api.telegram.org/bot{settings.BOT_TOKEN}/{method}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as error:
        try:
            result = json.load(error)
        except (ValueError, OSError, HTTPException):
            result = {}
        finally:
            error.close()
        parameters = result.get("parameters", {}) if isinstance(result, dict) else {}
        retry_after = parameters.get("retry_after") if isinstance(parameters, dict) else None
        raise TelegramAPIError(error.code, retry_after) from None
    except HTTPException:
        raise URLError("Telegram ulanishi uzildi.") from None
    if not isinstance(result, dict):
        raise RuntimeError("Telegram javobi yaroqsiz.")
    if result.get("ok") is not True:
        parameters = result.get("parameters", {})
        retry_after = parameters.get("retry_after") if isinstance(parameters, dict) else None
        raise TelegramAPIError(result.get("error_code"), retry_after)
    if "result" not in result:
        raise RuntimeError("Telegram javobi yaroqsiz.")
    return result["result"]
