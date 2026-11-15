from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class TelegramOnlyAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if not user.telegram_id or user.telegram_id <= 0:
            raise AuthenticationFailed("Telegram rejimida tasdiqlangan Telegram hisobi bilan kiring.")
        return user, token
