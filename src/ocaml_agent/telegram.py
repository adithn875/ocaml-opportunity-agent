import json
import os
import urllib.parse
import urllib.request


TELEGRAM_API = "https://api.telegram.org"


def send_message(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode()

    request = urllib.request.Request(url, data=data, method="POST")

    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode())

    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")


def send_long_message(text: str, max_length: int = 4000) -> None:
    if len(text) <= max_length:
        send_message(text)
        return

    chunks = []
    current = ""

    for line in text.splitlines():
        addition = line if not current else "\n" + line

        if len(current) + len(addition) <= max_length:
            current += addition
        else:
            if current:
                chunks.append(current)
            current = line

    if current:
        chunks.append(current)

    for chunk in chunks:
        send_message(chunk)
