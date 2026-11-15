from django.conf import settings


def welcome_message(update):
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    text = message.get("text", "")
    if not isinstance(chat, dict) or chat.get("type") != "private" or type(chat.get("id")) is not int:
        return None
    if not isinstance(text, str) or text.split(" ")[0] not in {"/start", "/menu"}:
        return None
    return {
        "chat_id": chat["id"],
        "text": "Tezkor’ga xush kelibsiz! 🍔\nSevimli taomingizni tanlang — biz yetkazamiz.",
        "reply_markup": {"inline_keyboard": [[{"text": "🍽 Menyuni ochish", "web_app": {"url": settings.WEBAPP_URL}}]]},
    }
